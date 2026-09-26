from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / '_cn_project' / 'tools'))
from pod3 import Pod3

HERE = Path(__file__).resolve().parent
NAME = r'WORLD\RU\A1_MANSION_PART4.TXT'
TAG = re.compile(rb'@@[^@]+@@')
before = Pod3.read(ROOT / '_cn_project/test_backup/a1_part4_softwrap_20260925/LANGUAGE.POD')
after = Pod3.read(HERE / 'payload/LANGUAGE.POD')
full = Pod3.read(ROOT / '_cn_project/test_backup/a1_text_isolation_20260925/LANGUAGE.POD')

def max_plain_run(blob: bytes) -> int:
    lengths = []
    for line in blob.splitlines():
        fields = line.split(b',', 2)
        if len(fields) != 3:
            continue
        for piece in TAG.split(fields[2]):
            lengths.extend(len(run) for run in re.findall(rb'\S+', piece))
    return max(lengths)

if sys.argv[1:] == ['--baseline']:
    assert before.read_entry(NAME) != full.read_entry(NAME)
    assert max_plain_run(full.read_entry(NAME)) == 100
    print('BASELINE_PASS part4=original chinese_unbroken_max=100')
elif sys.argv[1:] == ['--modified']:
    assert not after.verify_crcs()
    old = full.read_entry(NAME)
    new = after.read_entry(NAME)
    assert len(old.splitlines()) == len(new.splitlines()) == 143
    for a, b in zip(old.splitlines(), new.splitlines()):
        ac, bc = a.split(b',', 2), b.split(b',', 2)
        if len(ac) != 3:
            assert a == b
            continue
        assert ac[:2] == bc[:2]
        assert TAG.findall(ac[2]) == TAG.findall(bc[2])
        assert ac[2].replace(b' ', b'') == bc[2].replace(b' ', b'')
    assert max_plain_run(new) <= 48
    assert sum(before.read_entry(e.name) == after.read_entry(e.name)
               for e in before.entries) == 387
    print('MODIFIED_PASS part4=chinese changed_lines=43 max_unbroken=48 other_entries=387_unchanged crc=ok')
else:
    raise SystemExit('Expected --baseline or --modified')
