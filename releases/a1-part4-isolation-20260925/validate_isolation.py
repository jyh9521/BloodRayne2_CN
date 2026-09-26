from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / '_cn_project' / 'tools'))
from pod3 import Pod3

HERE = Path(__file__).resolve().parent
before = Pod3.read(ROOT / '_cn_project' / 'test_backup' /
                   'a1_part4_isolation_20260925' / 'LANGUAGE.POD')
after = Pod3.read(HERE / 'payload' / 'LANGUAGE.POD')
chinese = Pod3.read(ROOT / '_cn_project' / 'test_backup' /
                    'a1_text_isolation_20260925' / 'LANGUAGE.POD')
original = [rf'WORLD\RU\A1_MANSION_{name}.TXT'
            for name in ('PART1', 'PART2', 'PART3', 'ROOFARENA')]
part4 = r'WORLD\RU\A1_MANSION_PART4.TXT'

if sys.argv[1:] == ['--baseline']:
    assert all(before.read_entry(n) != chinese.read_entry(n) for n in original)
    assert before.read_entry(part4) != chinese.read_entry(part4)
    print('BASELINE_PASS a1_original=5 a1_chinese=0')
elif sys.argv[1:] == ['--modified']:
    assert not after.verify_crcs()
    assert all(after.read_entry(n) == chinese.read_entry(n) for n in original)
    assert after.read_entry(part4) == before.read_entry(part4)
    unchanged = sum(before.read_entry(e.name) == after.read_entry(e.name)
                    for e in before.entries)
    assert unchanged == 384
    print('MODIFIED_PASS a1_original=1 a1_chinese=4 other_entries=383_unchanged crc=ok')
else:
    raise SystemExit('Expected --baseline or --modified')
