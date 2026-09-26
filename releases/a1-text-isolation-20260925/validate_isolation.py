from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / '_cn_project' / 'tools'))
from pod3 import Pod3

RELEASE = Path(__file__).resolve().parent
names = [
    rf'WORLD\RU\A1_MANSION_{name}.TXT'
    for name in ('PART1', 'PART2', 'PART3', 'PART4', 'ROOFARENA')
]
original = Pod3.read(ROOT / '_cn_project' / 'baseline' / 'LANGUAGE.POD')
before = Pod3.read(ROOT / '_cn_project' / 'test_backup' /
                   'a1_text_isolation_20260925' / 'LANGUAGE.POD')
after = Pod3.read(RELEASE / 'payload' / 'LANGUAGE.POD')
assert not before.verify_crcs() and not after.verify_crcs()
if sys.argv[1:] == ['--baseline']:
    assert all(before.read_entry(name) != original.read_entry(name) for name in names)
    print('BASELINE_PASS A1_entries=5 translated=5 original=0')
elif sys.argv[1:] == ['--modified']:
    assert all(after.read_entry(name) == original.read_entry(name) for name in names)
    unchanged = sum(before.read_entry(e.name) == after.read_entry(e.name)
                    for e in before.entries)
    assert unchanged == 383
    print('MODIFIED_PASS A1_entries=5 original=5 other_entries=383_unchanged crc=ok')
else:
    raise SystemExit('Expected --baseline or --modified')
