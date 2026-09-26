"""Check SCB command structure and exact three-line insertion."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "_cn_project" / "tools"))
from pod3 import Pod3
from build import ENTRY, SAYS, split_scb

mode = sys.argv[1]
assert mode in {"baseline", "modified", "differential"}
baseline_path = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "COMMON.POD"
old = Pod3.read(baseline_path)
before = split_scb(old.read_entry(ENTRY))
assert old.entry_count == 3348
boxes = [line.replace(b"dbSay(", b"dbBoxedDisplay(", 1) for line in SAYS]
assert sum(line in before for line in SAYS) == 3
assert sum(line in before for line in boxes) == 0
if mode == "baseline":
    print(f"SCB_BASELINE commands={len(before)} target_says=3 boxed=0 entries={old.entry_count}")
    raise SystemExit(0)

new = Pod3.read(HERE / "payload" / "COMMON.POD")
after = split_scb(new.read_entry(ENTRY))
assert new.entry_count == old.entry_count
assert sum(line in after for line in boxes) == 3
assert len(after) == len(before) + 3
expected = []
for command in before:
    if command in SAYS:
        expected.append(command.replace(b"dbSay(", b"dbBoxedDisplay(", 1))
    expected.append(command)
assert after == expected
changed = [e.name for e in old.entries if old.read_entry(e.name) != new.read_entry(e.name)]
assert changed == [ENTRY], changed
print(f"SCB_MODIFIED commands={len(after)} target_says=3 boxed=3 changed_entries=1 entries={new.entry_count}")
