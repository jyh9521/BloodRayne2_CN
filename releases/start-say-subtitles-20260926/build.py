"""Add existing Chinese boxed captions before unboxed dbStartSay calls."""
from collections import Counter
from pathlib import Path
import csv
import hashlib
import re
import struct
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "_cn_project/tools"))
from pod3 import Pod3, Pod3File, rebuild_entries

OLD_COMMON = "2E39DECB4A6A823A7F4EF0BB8CAB38A51292ADF04B368283B37D5D45B4569186"
LANGUAGE = "BC758A173AE411003DF748BC4C4BF6C2E240B27E065D9A70B1DCDF9F51E3CE9C"
SOUND = "2990E799BCEEE41AECBFBD2399A9CFFE9BB298B668ACAA8FF60B38A1E55E9719"
START = re.compile(rb"^dbStartSay\(([^)]+)\)$", re.I)
BOX = re.compile(rb"^dbBoxedDisplay\(([^)]+)\)$", re.I)


def sha_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def scb(blob):
    version, count, text_size = struct.unpack_from("<III", blob)
    assert version == 1 and len(blob) == 12 + text_size + count * 4
    body = blob[12:12 + text_size]
    assert body.endswith(b"\0")
    commands = body[:-1].split(b"\0")
    assert len(commands) == count
    lines = list(struct.unpack_from("<" + "I" * count, blob, 12 + text_size))
    return commands, lines


def pack(commands, lines):
    assert len(commands) == len(lines)
    body = b"\0".join(commands) + b"\0"
    return struct.pack("<III", 1, len(commands), len(body)) + body + struct.pack("<" + "I" * len(lines), *lines)


def main():
    base = ROOT / "COMMON.POD"
    if sha_file(base) != OLD_COMMON:
        base = ROOT / "_cn_project/test_backup/start_say_subtitles_20260926/COMMON.POD"
    assert sha_file(base) == OLD_COMMON
    assert sha_file(ROOT / "LANGUAGE.POD") == LANGUAGE
    assert sha_file(ROOT / "W32ENSND.POD") == SOUND
    common = Pod3.read(base)
    language = Pod3.read(ROOT / "LANGUAGE.POD")
    sounds = Pod3File(ROOT / "W32ENSND.POD")
    replacements = {}
    audit = []
    diff = []
    unsupported = []
    for entry in common.entries:
        if not entry.name.upper().endswith(".SCB"):
            continue
        try:
            commands, lines = scb(common.read_entry(entry.name))
        except (AssertionError, ValueError, struct.error):
            unsupported.append(entry.name)
            continue
        ru = "WORLD\\RU\\" + entry.name.rsplit("\\", 1)[-1][:-4] + ".TXT"
        captions = {}
        if ru in language.by_name:
            for line in language.read_entry(ru).splitlines():
                parts = line.split(b",", 2)
                if len(parts) == 3:
                    captions[parts[0].strip().lower()] = parts[2].strip()
        out_cmd, out_lines = [], []
        local_add = 0
        for i, (command, source_line) in enumerate(zip(commands, lines)):
            match = START.match(command.strip())
            if match:
                key = match.group(1).strip().lower()
                lookup = key if key.endswith(b".wav") else key + b".wav"
                previous = BOX.match(commands[i - 1].strip()) if i else None
                paired = bool(previous and previous.group(1).strip().lower() == key)
                caption = captions.get(lookup) or captions.get(key)
                audio = "SOUND\\" + lookup.decode("ascii").upper()
                if paired:
                    status = "already_boxed"
                elif not caption:
                    status = "no_chinese_caption"
                elif audio not in sounds.by_name:
                    status = "no_audio"
                else:
                    status = "added"
                    display = b"dbBoxedDisplay(" + match.group(1) + b")"
                    out_cmd.append(display)
                    out_lines.append(source_line)
                    local_add += 1
                    diff.extend((f"@@ {entry.name} source_line={source_line} @@",
                                 "+" + display.decode("ascii"), " " + command.decode("ascii")))
                audit.append((entry.name, source_line, match.group(1).decode("ascii"),
                              "Rayne" if b"rayne" in key else "other", status, ru, audio))
            out_cmd.append(command)
            out_lines.append(source_line)
        if local_add:
            blob = pack(out_cmd, out_lines)
            assert scb(blob) == (out_cmd, out_lines)
            replacements[entry.name] = blob
    status = Counter(r[4] for r in audit)
    assert len(audit) == 224 and status == {"added": 210, "already_boxed": 11,
                                              "no_chinese_caption": 2, "no_audio": 1}
    assert sum(r[3] == "Rayne" and r[4] == "added" for r in audit) == 83
    assert sorted(unsupported) == [r"WORLD\0KAGAN.SCB", r"WORLD\PARTICLE_SPEED_TEST.SCB"]
    result = Pod3(rebuild_entries(common.data, replacements))
    assert not result.verify_crcs()
    assert len(result.entries) == len(common.entries)
    for entry in common.entries:
        assert result.read_entry(entry.name) == replacements.get(entry.name, common.read_entry(entry.name))
    (HERE / "payload").mkdir(exist_ok=True)
    (HERE / "payload/COMMON.POD").write_bytes(result.data)
    with (HERE / "audit.tsv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(("script", "source_line", "key", "speaker", "status", "ru_text_file", "audio_entry"))
        writer.writerows(audit)
    (HERE / "DIFF_FILE.diff").write_text("\n".join(diff) + "\n", encoding="utf-8")
    print(f"BUILD_OK startsay={len(audit)} added={status['added']} rayne_added=83 "
          f"changed_scb={len(replacements)} status={dict(status)} "
          f"common_sha256={hashlib.sha256(result.data).hexdigest().upper()}")


if __name__ == "__main__":
    main()
