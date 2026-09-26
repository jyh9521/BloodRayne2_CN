from pathlib import Path
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / '_cn_project/tools'))
from pod3 import Pod3

BACKUP = ROOT / '_cn_project/test_backup/all_dialogue_softwrap_20260926/LANGUAGE.POD'
BEFORE = BACKUP if BACKUP.exists() else ROOT / 'LANGUAGE.POD'
AFTER = HERE / 'payload/LANGUAGE.POD'
NAME_RE = re.compile(r'WORLD\\RU\\A[1-4][^\\]*\.TXT\Z')
TAG = re.compile(rb'@@[^@]+@@')

def runs(blob):
    for line in blob.splitlines():
        fields = line.split(b',', 2)
        if len(fields) != 3:
            continue
        for plain in TAG.split(fields[2]):
            for match in re.finditer(rb'\S+', plain):
                yield len(match.group())

before = Pod3.read(BEFORE)
after = Pod3.read(AFTER)
names = [entry.name for entry in before.entries if NAME_RE.fullmatch(entry.name)]
assert [entry.name for entry in before.entries] == [entry.name for entry in after.entries]
before_runs = [length for name in names for length in runs(before.read_entry(name))]
assert len([length for length in before_runs if length > 48]) == 478

if sys.argv[1:] == ['--baseline']:
    assert max(before_runs) == 114
    print(f'BASELINE_PASS stage_entries={len(names)} over_48=478 max_unbroken=114')
elif sys.argv[1:] == ['--modified']:
    manifest = json.loads((HERE / 'manifest.json').read_text(encoding='utf-8'))
    changed = []
    changed_lines = 0
    for entry in before.entries:
        name = entry.name
        old, new = before.read_entry(name), after.read_entry(name)
        if not NAME_RE.fullmatch(name):
            assert old == new
            continue
        assert len(old.splitlines()) == len(new.splitlines())
        for a, b in zip(old.splitlines(), new.splitlines()):
            ac, bc = a.split(b',', 2), b.split(b',', 2)
            assert len(ac) == len(bc)
            if len(ac) != 3:
                assert a == b
            else:
                assert ac[:2] == bc[:2]
                assert TAG.findall(ac[2]) == TAG.findall(bc[2])
                assert ac[2].replace(b' ', b'') == bc[2].replace(b' ', b'')
            changed_lines += a != b
        if old != new:
            changed.append(name)
    assert changed == list(manifest['entries'])
    assert len(changed) == 36 and changed_lines == 478
    after_runs = [length for name in names for length in runs(after.read_entry(name))]
    assert max(after_runs) <= 48
    assert not after.verify_crcs()
    print(f'MODIFIED_PASS stage_entries={len(names)} changed_entries=36 changed_lines=478 max_unbroken={max(after_runs)} other_entries=352_unchanged tags=preserved crc=ok')
else:
    raise SystemExit('Expected --baseline or --modified')
