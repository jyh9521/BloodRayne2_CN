"""Read-only source extraction for the scripted/engine Rayne voice inventory."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import sys
import wave
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "_cn_project" / "tools"))
from pod3 import Pod3File

PREVIOUS = ROOT / "_cn_project" / "releases" / "start-say-subtitles-20260926"
MAPPING = ROOT / "_cn_project" / "releases" / "fmv-full-20260925" / "character_map.json"
LEAD_MIN, TAIL_MIN, TAIL_COUNT = 0x81, 0xA1, 94


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def write_tsv(path: Path, columns: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, delimiter="\t", lineterminator="\r\n")
        writer.writeheader()
        writer.writerows(rows)


def parse_resource(blob: bytes) -> dict[str, tuple[str, bytes]]:
    result = {}
    for line in blob.splitlines():
        fields = line.split(b",", 2)
        if len(fields) != 3:
            continue
        key = fields[0].strip().decode("ascii", "replace").lower()
        actor = fields[1].strip().decode("cp1252", "replace")
        result[key] = (actor, fields[2].strip())
    return result


def decode_carrier(blob: bytes, reverse: dict[int, str]) -> str:
    out = []
    index = 0
    while index < len(blob):
        value = blob[index]
        if value < 0x80:
            out.append(chr(value))
            index += 1
            continue
        if index + 1 < len(blob):
            glyph = (value - LEAD_MIN) * TAIL_COUNT + blob[index + 1] - TAIL_MIN
            if glyph in reverse:
                out.append(reverse[glyph])
                index += 2
                continue
        out.append(f"<0x{value:02X}>")
        index += 1
    return "".join(out)


def normalize_key(key: str) -> str:
    return key.lower() if key.lower().endswith(".wav") else key.lower() + ".wav"


def speaker_from_key(key: str) -> str:
    base = key.rsplit("\\", 1)[-1]
    base = re.sub(r"^a\d+s\d+_", "", base, flags=re.I)
    base = re.sub(r"^a\d+_", "", base, flags=re.I)
    return base.split("_", 1)[0]


def voice_kind(prefix: str) -> str:
    term = prefix.removeprefix("Rayne_")
    if term.startswith("Ambient"):
        return "关卡环境自言自语"
    if term.startswith("Hint"):
        return "战斗/状态提示"
    if term in {"Guns", "Health", "Kick", "Rage"}:
        return "状态/操作语音类别"
    if term.startswith("Attack") or term.endswith("Attack"):
        return "攻击时语音"
    if term.startswith("GetHurt") or term.endswith("GetHurt"):
        return "受伤时语音"
    if term.startswith("Die") or term.endswith("Die"):
        return "死亡时语音"
    if term.startswith("Taunt") or term.endswith("Taunt"):
        return "嘲讽/战斗自言自语"
    if term.startswith("Kill") or term.endswith("Kill"):
        return "击杀时语音"
    if term.startswith("Elude") or term.endswith("Elude"):
        return "闪避/回避语音"
    return "其他战斗/反应语音"


def main() -> None:
    audit_path = PREVIOUS / "audit.tsv"
    cue_path = PREVIOUS / "engine_cue_inventory.tsv"
    source_hashes = {str(p.relative_to(ROOT)): sha(p) for p in (audit_path, cue_path, MAPPING, ROOT / "LANGUAGE.POD", ROOT / "W32ENSND.POD")}
    assert source_hashes[str(cue_path.relative_to(ROOT))] == "CBB916C908FBDD9E5FE3EC31CFAE66535890A7829D354D464FE9EDA8E8B7FA96"
    audit = read_tsv(audit_path)
    cues = read_tsv(cue_path)
    assert len(cues) == 72
    selected = [row for row in audit if row["status"] == "added" and row["speaker"] == "other"]
    assert len(selected) == 127
    language = Pod3File(ROOT / "LANGUAGE.POD")
    sounds = Pod3File(ROOT / "W32ENSND.POD")
    reverse = {index: char for char, index in json.loads(MAPPING.read_text(encoding="utf-8")).items()}
    resource_cache: dict[str, dict[str, tuple[str, bytes]]] = {}

    def resource(name: str) -> dict[str, tuple[str, bytes]]:
        if name not in resource_cache:
            resource_cache[name] = parse_resource(language.read_entry(name)) if name in language.by_name else {}
        return resource_cache[name]

    english_global: dict[str, tuple[str, bytes, str]] = {}
    for name in language.by_name:
        if name.startswith("WORLD\\EN\\") and name.endswith(".TXT"):
            for key, (actor, text) in resource(name).items():
                english_global.setdefault(key, (actor, text, name))

    scripted = []
    for row in selected:
        key = normalize_key(row["key"])
        english_name = row["ru_text_file"].replace("\\RU\\", "\\EN\\")
        english = resource(english_name).get(key)
        english_source = english_name
        if not english and key in english_global:
            actor, blob, english_source = english_global[key]
            english = (actor, blob)
        chinese = resource(row["ru_text_file"]).get(key)
        assert english is not None and chinese is not None, row
        scripted.append({
            "script": row["script"], "source_line": row["source_line"],
            "key": row["key"], "speaker_hint": speaker_from_key(row["key"]),
            "actor_token": english[0], "english": english[1].decode("cp1252", "replace"),
            "current_chinese": decode_carrier(chinese[1], reverse),
            "audio_entry": row["audio_entry"], "english_source": english_source,
            "chinese_source": row["ru_text_file"],
        })
    write_tsv(HERE / "scripted_other_speech.tsv", list(scripted[0]), scripted)

    sample_to_ids: dict[str, list[str]] = defaultdict(list)
    categories = []
    for cue in cues:
        prefix = cue["cue_prefix"]
        sample_names = sorted(name for name in sounds.by_name if name.upper().startswith("SOUND\\" + prefix.upper() + "_") and name.upper().endswith(".WAV"))
        assert len(sample_names) == int(cue["english_wav_count"]), prefix
        for name in sample_names:
            sample_to_ids[name].append(cue["cue_id"])
        categories.append({
            "cue_id": cue["cue_id"], "cue_prefix": prefix, "meaning_hint": voice_kind(prefix),
            "english_wav_count": len(sample_names), "sample_files": "; ".join(name.rsplit("\\", 1)[-1] for name in sample_names),
            "status": "有英语音频；台词需人工确认" if sample_names else "此音频包未找到匹配 WAV",
        })
    write_tsv(HERE / "engine_rayne_categories.tsv", list(categories[0]), categories)

    samples = []
    for name, ids in sorted(sample_to_ids.items()):
        blob = sounds.read_entry(name)
        try:
            with wave.open(io.BytesIO(blob), "rb") as reader:
                duration = reader.getnframes() / reader.getframerate()
        except (wave.Error, ZeroDivisionError):
            duration = 0.0
        sample_key = name.rsplit("\\", 1)[-1].lower()
        existing = english_global.get(sample_key)
        samples.append({
            "cue_ids": ",".join(ids), "category": next(row["cue_prefix"] for row in cues if row["cue_id"] == ids[0]),
            "audio_entry": name, "duration_s": f"{duration:.2f}", "english_resource_text": existing[1].decode("cp1252", "replace") if existing else "",
            "asr_draft_english": "", "asr_status": "not_transcribed", "review_note": "",
        })
    write_tsv(HERE / "engine_rayne_samples.tsv", list(samples[0]), samples)
    (HERE / "source_hashes.json").write_text(json.dumps(source_hashes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"EXTRACT_OK scripted_other={len(scripted)} unique_keys={len({x['key'].lower() for x in scripted})} categories={len(categories)} unique_wav={len(samples)} existing_english={sum(bool(x['english_resource_text']) for x in samples)}")
    print("SPEAKER_HINT_COUNTS " + "; ".join(f"{key}:{value}" for key, value in Counter(x["speaker_hint"] for x in scripted).most_common()))


if __name__ == "__main__":
    main()
