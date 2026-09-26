from pathlib import Path
import hashlib
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / '_cn_project/tools'))
from pod3 import Pod3

NAME = r'WORLD\RU\A1_MANSION_ROOFARENA.TXT'
TAG = re.compile(rb'@@[^@]+@@')
BEFORE = ROOT / '_cn_project/test_backup/a1_roof_softwrap_20260925/LANGUAGE.POD'
AFTER = HERE / 'payload/LANGUAGE.POD'

def max_run(blob):
    runs = []
    for line in blob.splitlines():
        fields = line.split(b',', 2)
        if len(fields) == 3:
            for plain in TAG.split(fields[2]):
                runs.extend(len(run) for run in re.findall(rb'\S+', plain))
    return max(runs)

before = Pod3.read(BEFORE)
after = Pod3.read(AFTER)
old, new = before.read_entry(NAME), after.read_entry(NAME)
assert not before.verify_crcs() and not after.verify_crcs()
assert len(old.splitlines()) == len(new.splitlines()) == 21

if sys.argv[1:] == ['--baseline']:
    assert max_run(old) == 82
    print('BASELINE_PASS roof=chinese max_unbroken=82')
elif sys.argv[1:] == ['--modified']:
    for a, b in zip(old.splitlines(), new.splitlines()):
        ac, bc = a.split(b',', 2), b.split(b',', 2)
        assert len(ac) == len(bc)
        if len(ac) != 3:
            assert a == b
        else:
            assert ac[:2] == bc[:2]
            assert TAG.findall(ac[2]) == TAG.findall(bc[2])
            assert ac[2].replace(b' ', b'') == bc[2].replace(b' ', b'')
    manifest = json.loads((HERE / 'manifest.json').read_text(encoding='utf-8'))
    assert max_run(new) <= 48
    assert sum(before.read_entry(e.name) == after.read_entry(e.name) for e in before.entries) == 387
    assert sum(a != b for a, b in zip(old.splitlines(), new.splitlines())) == manifest['changed_lines']
    print(f"MODIFIED_PASS roof=chinese changed_lines={manifest['changed_lines']} max_unbroken={max_run(new)} other_entries=387_unchanged crc=ok")
else:
    raise SystemExit('Expected --baseline or --modified')
