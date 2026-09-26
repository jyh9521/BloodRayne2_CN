"""Cover scripted speech that has audio and Chinese text but no boxed subtitle."""
from collections import defaultdict
from pathlib import Path
import csv
import hashlib
import json
import re
import struct
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "_cn_project" / "tools"))
sys.path.insert(0, str(ROOT / "_cn_project" / "releases" / "a1-part4-softwrap-20260925"))
from pod3 import Pod3, Pod3File, rebuild_entries
from build_full_translation import encode_text, carrier_pair
from build_softwrap import softwrap

COMMON_SHA = "7E07F40F473DC056D289D6F583EAB4A890FD9CEA72BAB667E23E70CEE70C4EE3"
LANGUAGE_SHA = "18B5FA66F69AD57327D91C54BFD08F3FD9DC34A7C76E15FF53FDBA22F8D35C97"
SOUND_SHA = "2990E799BCEEE41AECBFBD2399A9CFFE9BB298B668ACAA8FF60B38A1E55E9719"
SAY = re.compile(rb"^dbSay\(([^)]+)\)$", re.I)
BOX = re.compile(rb"^dbBoxedDisplay\(([^)]+)\)$", re.I)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def fields(line: bytes) -> list[bytes]:
    return line.rstrip(b"\r\n").split(b",", 2)


def key_of(line: bytes) -> bytes:
    return fields(line)[0].strip().lower()


def caption_map(pod: Pod3, name: str) -> dict[bytes, bytes]:
    if name not in pod.by_name:
        return {}
    result = {}
    for line in pod.read_entry(name).splitlines():
        parts = fields(line)
        if len(parts) == 3:
            result[parts[0].strip().lower()] = parts[2].strip()
    return result


def split_scb(blob: bytes) -> tuple[list[bytes], list[int]]:
    version, count, text_size = struct.unpack_from("<III", blob)
    assert version == 1 and len(blob) == 12 + text_size + count * 4
    body = blob[12:12 + text_size]
    assert body.endswith(b"\0")
    commands = body[:-1].split(b"\0")
    assert len(commands) == count
    source_lines = list(struct.unpack_from("<" + "I" * count, blob, 12 + text_size))
    return commands, source_lines


def encode_scb(commands: list[bytes], source_lines: list[int]) -> bytes:
    assert len(commands) == len(source_lines)
    body = b"\0".join(commands) + b"\0"
    return (struct.pack("<III", 1, len(commands), len(body)) + body
            + struct.pack("<" + "I" * len(source_lines), *source_lines))


def make_language(current: Pod3) -> Pod3:
    mapping = json.loads((ROOT / "_cn_project/releases/fmv-full-20260925/character_map.json").read_text(encoding="utf-8"))
    punctuation = {bytes(carrier_pair(mapping[ch])) for ch in "，。！？；：、" if ch in mapping}
    with (HERE / "new_translations.tsv").open(encoding="utf-8", newline="") as stream:
        translations = {r["key"]: r["translation_zh"] for r in csv.DictReader(stream, delimiter="\t")}
    assert len(translations) == 4
    source = r"WORLD\RU\A2_SUBWAY1.TXT"
    old_lines = current.read_entry(source).splitlines(keepends=True)
    output = []
    corrected = 0
    for line in old_lines:
        if key_of(line) == b"2s5_rayne_1.wav":
            line = b"a" + line
            corrected += 1
        output.append(line)
    assert corrected == 1
    replacements = {source: b"".join(output)}

    source = r"WORLD\RU\A3_SHROUDTOWER_ASCENT.TXT"
    donor = current.read_entry(r"WORLD\RU\A2_SEWER_SLEZZARENA.TXT")
    matches = [line for line in donor.splitlines() if key_of(line) == b"a2s4_severin_10.wav"]
    assert len(matches) == 1
    assert b"a2s4_severin_10.wav" not in caption_map(current, source)
    replacements[source] = current.read_entry(source) + b"\r\n" + matches[0] + b"\r\n"

    source = r"WORLD\RU\A4_PARK_2.TXT"
    existing = caption_map(current, source)
    additions = []
    for key in ("a4s1_severin_22.wav", "a4s1_rayne_28.wav"):
        assert key.encode() not in existing
        coded = softwrap(encode_text(translations[key], mapping), punctuation)
        assert coded and max(map(len, re.findall(rb"\S+", coded))) <= 48
        additions.append(key.encode() + b", $, " + coded + b"\r\n")
    replacements[source] = current.read_entry(source) + b"\r\n" + b"".join(additions)
    donor = current.read_entry(r"WORLD\RU\A4_KAGANSTOWER_BIOARMOR.TXT")
    wanted = {b"a4s3_xerx_13.wav", b"a4s3_xerx_14.wav", b"a4s3_rayne_16.wav",
              b"a4s3_rayne_17.wav", b"a4s3_rayne_18.wav"}
    shared_lines = [line for line in donor.splitlines() if key_of(line) in wanted]
    assert len(shared_lines) == len(wanted)
    debug_ru = r"WORLD\RU\0BIOARMOR.TXT"
    result = Pod3(rebuild_entries(current.data, replacements,
                                  {debug_ru: b"\r\n".join(shared_lines) + b"\r\n"}))
    assert not result.verify_crcs()
    assert sorted(e.name for e in current.entries if current.read_entry(e.name) != result.read_entry(e.name)) == sorted(replacements)
    assert result.read_entry(debug_ru) == b"\r\n".join(shared_lines) + b"\r\n"
    return result


def main() -> None:
    backup = ROOT / "_cn_project/test_backup/boxed_dialogue_coverage_20260926"
    common_path = ROOT / "COMMON.POD"
    language_path = ROOT / "LANGUAGE.POD"
    if sha_file(common_path) != COMMON_SHA:
        common_path = backup / "COMMON.POD"
    if sha_file(language_path) != LANGUAGE_SHA:
        language_path = backup / "LANGUAGE.POD"
    common = Pod3.read(common_path)
    language = Pod3.read(language_path)
    sounds = Pod3File(ROOT / "W32ENSND.POD")
    assert sha(common.data) == COMMON_SHA
    assert sha(language.data) == LANGUAGE_SHA
    assert sha_file(ROOT / "W32ENSND.POD") == SOUND_SHA
    new_language = make_language(language)

    replacements = {}
    audit = []
    diff = [
        "@@ LANGUAGE.POD WORLD\\RU\\A2_SUBWAY1.TXT @@",
        "-2s5_rayne_1.wav -> +a2s5_rayne_1.wav (existing Chinese text unchanged)",
        "@@ LANGUAGE.POD WORLD\\RU\\A3_SHROUDTOWER_ASCENT.TXT @@",
        "+a2s4_severin_10.wav (copied from A2_SEWER_SLEZZARENA.TXT)",
        "@@ LANGUAGE.POD WORLD\\RU\\A4_PARK_2.TXT @@",
        "+a4s1_severin_22.wav and +a4s1_rayne_28.wav (translated audio)",
        "@@ LANGUAGE.POD WORLD\\RU\\0BIOARMOR.TXT @@",
        "+five existing Chinese rows copied from A4_KAGANSTOWER_BIOARMOR.TXT",
    ]
    added = 0
    unsupported = []
    for entry in common.entries:
        if not entry.name.upper().endswith(".SCB"):
            continue
        try:
            commands, source_lines = split_scb(common.read_entry(entry.name))
        except (AssertionError, ValueError, struct.error):
            unsupported.append(entry.name)
            continue
        ru = "WORLD\\RU\\" + entry.name.rsplit("\\", 1)[-1][:-4] + ".TXT"
        captions = caption_map(new_language, ru)
        existing_boxes = {m.group(1).lower() for command in commands if (m := BOX.match(command.strip()))}
        output_commands = []
        output_lines = []
        local_added = 0
        for command, source_line in zip(commands, source_lines):
            match = SAY.match(command.strip())
            if match:
                key = match.group(1).strip().lower()
                lookup = key if key.endswith(b".wav") else key + b".wav"
                text = captions.get(key) or captions.get(lookup)
                audio_name = "SOUND\\" + lookup.decode("ascii").upper()
                if key in existing_boxes:
                    status = "already_boxed"
                elif ru not in new_language.by_name:
                    status = "no_ru_script"
                elif not text:
                    status = "no_chinese_caption"
                elif audio_name not in sounds.by_name:
                    status = "no_audio"
                else:
                    status = "added"
                    assert command == command.strip()
                    display = b"dbBoxedDisplay(" + match.group(1) + b")"
                    output_commands.append(display)
                    output_lines.append(source_line)
                    local_added += 1
                    added += 1
                    diff.extend((f"@@ {entry.name} source_line={source_line} @@",
                                 "+" + display.decode("ascii"),
                                 " " + command.decode("ascii")))
                audit.append((entry.name, source_line, match.group(1).decode("ascii"), status, ru, audio_name))
            output_commands.append(command)
            output_lines.append(source_line)
        if local_added:
            replacement = encode_scb(output_commands, output_lines)
            assert split_scb(replacement) == (output_commands, output_lines)
            replacements[entry.name] = replacement
    assert added == 417, added
    assert len(replacements) == 32, len(replacements)
    assert len(audit) == 502, len(audit)
    assert sorted(unsupported) == [r"WORLD\0KAGAN.SCB", r"WORLD\PARTICLE_SPEED_TEST.SCB"]

    new_common = Pod3(rebuild_entries(common.data, replacements))
    assert not new_common.verify_crcs()
    assert new_common.entry_count == common.entry_count
    for entry in common.entries:
        expected = replacements.get(entry.name, common.read_entry(entry.name))
        assert new_common.read_entry(entry.name) == expected
    payload = HERE / "payload"
    payload.mkdir(parents=True, exist_ok=True)
    (payload / "LANGUAGE.POD").write_bytes(new_language.data)
    (payload / "COMMON.POD").write_bytes(new_common.data)
    with (HERE / "audit.tsv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, delimiter="\t")
        writer.writerow(("script", "source_line", "key", "status", "ru_text_file", "audio_entry"))
        writer.writerows(audit)
    (HERE / "DIFF_FILE.diff").write_text("\n".join(diff) + "\n", encoding="utf-8")
    from collections import Counter
    print(f"BUILD_OK says={len(audit)} added={added} changed_scb={len(replacements)} "
          f"status={dict(Counter(row[3] for row in audit))} "
          f"common_sha256={sha(new_common.data)} language_sha256={sha(new_language.data)}")


if __name__ == "__main__":
    main()
