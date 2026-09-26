"""Independent structural verification of boxed subtitle coverage."""
from collections import Counter
from pathlib import Path
import csv
import hashlib
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "_cn_project" / "tools"))
from pod3 import Pod3

SAY = re.compile(rb"^dbSay\(([^)]+)\)$", re.I)
BOX = re.compile(rb"^dbBoxedDisplay\(([^)]+)\)$", re.I)
OLD_HASHES = {
    "COMMON.POD": "7E07F40F473DC056D289D6F583EAB4A890FD9CEA72BAB667E23E70CEE70C4EE3",
    "LANGUAGE.POD": "18B5FA66F69AD57327D91C54BFD08F3FD9DC34A7C76E15FF53FDBA22F8D35C97",
}


def baseline_pod(name):
    candidate = ROOT / name
    if hashlib.sha256(candidate.read_bytes()).hexdigest().upper() != OLD_HASHES[name]:
        candidate = ROOT / "_cn_project/test_backup/boxed_dialogue_coverage_20260926" / name
    data = candidate.read_bytes()
    assert hashlib.sha256(data).hexdigest().upper() == OLD_HASHES[name]
    return Pod3(data)


def split(blob):
    import struct
    version, count, size = struct.unpack_from("<III", blob)
    assert version == 1 and len(blob) == 12 + size + count * 4
    commands = blob[12:12 + size - 1].split(b"\0")
    lines = struct.unpack_from("<" + "I" * count, blob, 12 + size)
    assert len(commands) == count
    return list(commands), list(lines)


def scan(pod):
    result = []
    unsupported = []
    unmatched_say = []
    for entry in pod.entries:
        if not entry.name.upper().endswith(".SCB"):
            continue
        try:
            commands, lines = split(pod.read_entry(entry.name))
        except (AssertionError, ValueError):
            unsupported.append(entry.name)
            continue
        for i, command in enumerate(commands):
            match = SAY.match(command.strip())
            if match:
                preceding = BOX.match(commands[i - 1].strip()) if i else None
                paired = bool(preceding and preceding.group(1).lower() == match.group(1).lower())
                result.append((entry.name, match.group(1).lower(), paired))
            elif b"dbsay" in command.lower():
                unmatched_say.append((entry.name, command))
    assert not unmatched_say, unmatched_say[:10]
    return result, unsupported


def main(mode):
    if mode == "baseline":
        common = baseline_pod("COMMON.POD")
        language = baseline_pod("LANGUAGE.POD")
        rows, unsupported = scan(common)
        assert len(rows) == 502 and sum(row[2] for row in rows) == 82
        assert len(unsupported) == 2
        print(f"BASELINE_OK says={len(rows)} boxed={sum(row[2] for row in rows)} "
              f"unboxed={sum(not row[2] for row in rows)} unsupported={len(unsupported)} "
              f"common_entries={len(common.entries)} language_entries={len(language.entries)}")
        return
    assert mode == "modified"
    old_common = baseline_pod("COMMON.POD")
    old_language = baseline_pod("LANGUAGE.POD")
    common = Pod3.read(HERE / "payload" / "COMMON.POD")
    language = Pod3.read(HERE / "payload" / "LANGUAGE.POD")
    baseline, unsupported = scan(old_common)
    modified, unsupported_new = scan(common)
    assert unsupported_new == unsupported
    assert [(a, b) for a, b, _ in baseline] == [(a, b) for a, b, _ in modified]
    assert len(modified) == 502 and sum(row[2] for row in modified) == 499
    assert sum(not row[2] for row in modified) == 3
    changed_scb = []
    for entry in old_common.entries:
        before = old_common.read_entry(entry.name)
        after = common.read_entry(entry.name)
        if before == after:
            continue
        assert entry.name.upper().endswith(".SCB")
        a_cmd, a_lines = split(before)
        b_cmd, b_lines = split(after)
        j = 0
        for i, cmd in enumerate(a_cmd):
            match = SAY.match(cmd.strip())
            if match and j < len(b_cmd) and BOX.match(b_cmd[j].strip()):
                box = BOX.match(b_cmd[j].strip())
                if box.group(1).lower() == match.group(1).lower() and not (
                    i and (old_box := BOX.match(a_cmd[i - 1].strip()))
                    and old_box.group(1).lower() == match.group(1).lower()
                ):
                    assert b_lines[j] == a_lines[i]
                    j += 1
            assert b_cmd[j] == cmd and b_lines[j] == a_lines[i]
            j += 1
        assert j == len(b_cmd)
        changed_scb.append(entry.name)
    assert len(changed_scb) == 32
    assert len(common.entries) == len(old_common.entries)
    language_changed = [e.name for e in old_language.entries
                        if old_language.read_entry(e.name) != language.read_entry(e.name)]
    language_added = set(language.by_name) - set(old_language.by_name)
    assert len(language_changed) == 3 and language_added == {r"WORLD\RU\0BIOARMOR.TXT"}
    assert len(language.entries) == len(old_language.entries) + 1
    with (HERE / "audit.tsv").open(encoding="utf-8", newline="") as stream:
        audit = list(csv.DictReader(stream, delimiter="\t"))
    statuses = Counter(r["status"] for r in audit)
    assert statuses == {"added": 417, "already_boxed": 82,
                        "no_chinese_caption": 2, "no_audio": 1}
    assert not common.verify_crcs() and not language.verify_crcs()
    print(f"MODIFIED_OK says={len(modified)} boxed={sum(row[2] for row in modified)} "
          f"unboxed={sum(not row[2] for row in modified)} added={statuses['added']} "
          f"changed_scb={len(changed_scb)} language_changed={len(language_changed)} "
          f"language_added={len(language_added)} crc_failures=0")


if __name__ == "__main__":
    main(sys.argv[1])
