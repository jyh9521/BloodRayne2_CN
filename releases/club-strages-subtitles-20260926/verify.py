"""Check that only three subtitle speaker fields changed."""
from pathlib import Path
import hashlib
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "_cn_project" / "tools"))
from pod3 import Pod3

old = Pod3.read(ROOT / "LANGUAGE.POD") if len(sys.argv) == 1 else Pod3.read(Path(sys.argv[1]))
new = Pod3.read(HERE / "payload" / "LANGUAGE.POD")
target = r"WORLD\RU\A2_UNIONSTATION_PART3.TXT"
speakers = {
    b"a2s2_severin_9.wav": b" SEVERIN",
    b"a2s2_rayne_26.wav": b" RAYNE",
    b"a2s2_severin_10.wav": b" SEVERIN",
}
assert old.entry_count == new.entry_count == 392
assert not old.verify_crcs() and not new.verify_crcs()
changed = [e.name for e in old.entries if old.read_entry(e.name) != new.read_entry(e.name)]
assert changed == [target], changed
old_lines = old.read_entry(target).splitlines(keepends=True)
new_lines = new.read_entry(target).splitlines(keepends=True)
assert len(old_lines) == len(new_lines)
count = 0
for before, after in zip(old_lines, new_lines):
    if before == after:
        continue
    original_fields = before.rstrip(b"\r\n").split(b",", 2)
    modified_fields = after.rstrip(b"\r\n").split(b",", 2)
    assert len(original_fields) == len(modified_fields) == 3
    key = original_fields[0].strip().lower()
    assert key in speakers and original_fields[1] == b" $"
    assert modified_fields == [original_fields[0], speakers[key], original_fields[2]]
    count += 1
assert count == 3
print("SUBTITLE_METADATA changed_entries=1 speaker_fields=3 text_bytes=unchanged crc_failures=0")
