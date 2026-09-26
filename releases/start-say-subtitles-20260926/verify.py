"""Independently check dbStartSay caption insertions and unchanged resources."""
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
from pod3 import Pod3

OLD = "2E39DECB4A6A823A7F4EF0BB8CAB38A51292ADF04B368283B37D5D45B4569186"
NEW = "AB7EAEB666B74A8131E146A2E8764366CCD92305A08518E064B06D9FEEDDE844"
START = re.compile(rb"^dbStartSay\(([^)]+)\)$", re.I)
BOX = re.compile(rb"^dbBoxedDisplay\(([^)]+)\)$", re.I)


def baseline():
    path = ROOT / "COMMON.POD"
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest().upper() != OLD:
        data = (ROOT / "_cn_project/test_backup/start_say_subtitles_20260926/COMMON.POD").read_bytes()
    assert hashlib.sha256(data).hexdigest().upper() == OLD
    return Pod3(data)


def split(blob):
    version, count, size = struct.unpack_from("<III", blob)
    assert version == 1 and len(blob) == 12 + size + count * 4
    body = blob[12:12 + size]
    assert body.endswith(b"\0")
    commands = body[:-1].split(b"\0")
    assert len(commands) == count
    return commands, list(struct.unpack_from("<" + "I" * count, blob, 12 + size))


def scan(pod):
    result = []
    unsupported = []
    for entry in pod.entries:
        if not entry.name.upper().endswith(".SCB"):
            continue
        try:
            commands, _ = split(pod.read_entry(entry.name))
        except (AssertionError, ValueError):
            unsupported.append(entry.name)
            continue
        for i, command in enumerate(commands):
            match = START.match(command.strip())
            if match:
                prior = BOX.match(commands[i - 1].strip()) if i else None
                result.append((entry.name, match.group(1).lower(),
                               bool(prior and prior.group(1).lower() == match.group(1).lower())))
            elif b"dbstartsay" in command.lower():
                raise AssertionError((entry.name, command))
    return result, unsupported


def main(mode):
    old = baseline()
    a, unsupported = scan(old)
    assert len(a) == 224 and sum(row[2] for row in a) == 11 and len(unsupported) == 2
    if mode == "baseline":
        print(f"BASELINE_OK startsay={len(a)} boxed=11 unboxed=213 unsupported=2 entries={len(old.entries)}")
        return
    assert mode == "modified"
    new = Pod3.read(HERE / "payload/COMMON.POD")
    assert hashlib.sha256(new.data).hexdigest().upper() == NEW
    b, unsupported_new = scan(new)
    assert unsupported_new == unsupported
    assert [(x, y) for x, y, _ in a] == [(x, y) for x, y, _ in b]
    assert len(b) == 224 and sum(row[2] for row in b) == 221
    changed = 0
    for entry in old.entries:
        before, after = old.read_entry(entry.name), new.read_entry(entry.name)
        if before == after:
            continue
        assert entry.name.upper().endswith(".SCB")
        ac, al = split(before)
        bc, bl = split(after)
        j = 0
        for i, command in enumerate(ac):
            match = START.match(command.strip())
            prior = BOX.match(ac[i - 1].strip()) if i else None
            already = bool(match and prior and prior.group(1).lower() == match.group(1).lower())
            if match and not already and j < len(bc):
                candidate = BOX.match(bc[j].strip())
                if candidate and candidate.group(1).lower() == match.group(1).lower():
                    assert bl[j] == al[i]
                    j += 1
            assert bc[j] == command and bl[j] == al[i]
            j += 1
        assert j == len(bc)
        changed += 1
    with (HERE / "audit.tsv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    status = Counter(row["status"] for row in rows)
    assert status == {"added": 210, "already_boxed": 11,
                      "no_chinese_caption": 2, "no_audio": 1}
    assert sum(r["speaker"] == "Rayne" and r["status"] == "added" for r in rows) == 83
    assert changed == 28 and len(new.entries) == len(old.entries) and not new.verify_crcs()
    print("MODIFIED_OK startsay=224 boxed=221 unboxed=3 added=210 rayne_added=83 "
          "changed_scb=28 unchanged_entries=3320 crc_failures=0")


if __name__ == "__main__":
    main(sys.argv[1])
