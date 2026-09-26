"""Build a bounded carrier-font and engine-voice caption payload on copies."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "_cn_project" / "tools"))
from build_full_translation import build_font_texture, carrier_pair, encode_text, TARGET_TEX_NAME
from pod3 import Pod3, rebuild_entries
from tex_rgba import write_tex

BASE_MAP = ROOT / "_cn_project" / "releases" / "fmv-full-20260925" / "character_map.json"
VOICE_FILE = HERE / "voice_subtitles_zh.tsv"
EXPECTED = {
    "dinput8.dll": "9E2CE9D0127EEE76E4D6C2C5097FF975B5B8F2F9CF2D0FE489AF354C5782B1A9",
    "LANGUAGE.POD": "BC758A173AE411003DF748BC4C4BF6C2E240B27E065D9A70B1DCDF9F51E3CE9C",
    "COMMON.POD": "AB7EAEB666B74A8131E146A2E8764366CCD92305A08518E064B06D9FEEDDE844",
    "W32ENSND.POD": "2990E799BCEEE41AECBFBD2399A9CFFE9BB298B668ACAA8FF60B38A1E55E9719",
}


def sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest().upper()


def main() -> None:
    for name, expected in EXPECTED.items():
        assert sha((ROOT / name).read_bytes()) == expected, name
    with VOICE_FILE.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    assert len(rows) == 253 and len({row["audio_entry"].upper() for row in rows}) == 253
    mapping = json.loads(BASE_MAP.read_text(encoding="utf-8"))
    extras = sorted({c for row in rows for c in row["translation_zh"] if ord(c) >= 128 and c not in mapping}, key=ord)
    for c in extras:
        mapping[c] = len(mapping)
    assert len(mapping) < 2914
    header = ["#pragma once", "struct VoiceCaptionRow { const char* stem; const char* carrier; float seconds; };", ""]
    table = []
    max_bytes = 0
    max_unique = 0
    for index, row in enumerate(rows):
        text = row["translation_zh"]
        assert text and all(c not in text for c in "\r\n\t\0")
        body = encode_text(text, mapping)
        unique = len({c for c in text if ord(c) >= 128})
        # The game's boxed display copies into a 256-byte object buffer at
        # +0x3F0. Keep a much tighter 96-byte ceiling and atlas slot ceiling.
        assert len(body) <= 96 and unique <= 80, (index, len(body), unique)
        max_bytes = max(max_bytes, len(body))
        max_unique = max(max_unique, unique)
        stem = row["audio_entry"].rsplit("\\", 1)[-1].removesuffix(".WAV")
        assert stem.upper().startswith("RAYNE_") and len(stem) <= 48
        duration = float(row["duration_s"])
        assert math.isfinite(duration) and 0 < duration < 20
        seconds = min(10.0, max(1.5, duration + 0.30, len(text) * 0.12 + 0.5))
        header.append(f"static const char kVoiceText{index:03d}[] = {{{', '.join(f'static_cast<char>(0x{b:02X})' for b in body)}, 0}};")
        table.append(f'    {{"{stem}", kVoiceText{index:03d}, {seconds:.2f}f}},')
    header.extend(("", "static const VoiceCaptionRow kVoiceCaptions[] = {", *table, "};", ""))
    (HERE / "source" / "voice_subtitles.h").write_text("\n".join(header), encoding="ascii")
    (HERE / "character_map.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tex_header, image = build_font_texture(mapping)
    tex_path = HERE / "font" / "GOTHICTITLE_RU.TEX"
    tex_path.parent.mkdir(exist_ok=True)
    write_tex(tex_path, tex_header, image)
    original = Pod3.read(ROOT / "LANGUAGE.POD")
    built = Pod3(rebuild_entries(original.data, {TARGET_TEX_NAME: tex_path.read_bytes()}))
    assert not built.verify_crcs()
    changed = [entry.name for entry in original.entries if original.read_entry(entry.name) != built.read_entry(entry.name)]
    assert changed == [TARGET_TEX_NAME]
    payload = HERE / "payload" / "LANGUAGE.POD"
    payload.parent.mkdir(exist_ok=True)
    payload.write_bytes(built.data)
    manifest = {
        "before": EXPECTED, "language_after": sha(built.data),
        "font_before": sha(original.read_entry(TARGET_TEX_NAME)),
        "font_after": sha(tex_path.read_bytes()),
        "translation_rows": len(rows), "new_glyphs": len(extras),
        "max_caption_bytes": max_bytes, "max_distinct_glyphs": max_unique,
        "changed_language_entries": changed,
        "voice_call_rva": "0x151F72", "caption_function_rva": "0xF4560",
    }
    (HERE / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"BUILD_OK captions={len(rows)} glyphs_added={len(extras)} max_bytes={max_bytes} max_unique={max_unique} language_changed_entries=1 sha256={sha(built.data)}")


if __name__ == "__main__":
    main()
