"""Give the three Club Strages opening radio lines explicit speaker fields."""
from pathlib import Path
import hashlib
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "_cn_project" / "tools"))
from pod3 import Pod3, rebuild_entries

BEFORE = "18B5FA66F69AD57327D91C54BFD08F3FD9DC34A7C76E15FF53FDBA22F8D35C97"
ENTRY = r"WORLD\RU\A2_UNIONSTATION_PART3.TXT"
SPEAKERS = {
    b"a2s2_severin_9.wav": b" SEVERIN",
    b"a2s2_rayne_26.wav": b" RAYNE",
    b"a2s2_severin_10.wav": b" SEVERIN",
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def main() -> None:
    old = Pod3.read(ROOT / "LANGUAGE.POD")
    assert sha(old.data) == BEFORE
    original = old.read_entry(ENTRY)
    output: list[bytes] = []
    changed: set[bytes] = set()
    for line in original.splitlines(keepends=True):
        fields = line.rstrip(b"\r\n").split(b",", 2)
        if len(fields) == 3 and fields[0].strip().lower() in SPEAKERS:
            key = fields[0].strip().lower()
            assert fields[1] == b" $", (key, fields[1])
            fields[1] = SPEAKERS[key]
            ending = line[len(line.rstrip(b"\r\n")):]
            line = b",".join(fields) + ending
            assert key not in changed
            changed.add(key)
        output.append(line)
    assert changed == set(SPEAKERS)
    replacement = b"".join(output)
    modified = Pod3(rebuild_entries(old.data, {ENTRY: replacement}))
    assert not modified.verify_crcs()
    assert modified.entry_count == old.entry_count
    for entry in old.entries:
        if entry.name != ENTRY:
            assert modified.read_entry(entry.name) == old.read_entry(entry.name)
    payload = HERE / "payload" / "LANGUAGE.POD"
    payload.parent.mkdir(parents=True, exist_ok=True)
    payload.write_bytes(modified.data)
    print(f"BUILD_OK changed_entry={ENTRY} speaker_fields=3 unchanged_entries={old.entry_count - 1} sha256={sha(modified.data)}")


if __name__ == "__main__":
    main()
