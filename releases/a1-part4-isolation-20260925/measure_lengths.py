from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / '_cn_project' / 'tools'))
from pod3 import Pod3

chinese = Pod3.read(ROOT / '_cn_project' / 'test_backup' /
                    'a1_text_isolation_20260925' / 'LANGUAGE.POD')
original = Pod3.read(ROOT / '_cn_project' / 'baseline' / 'LANGUAGE.POD')
names = [rf'WORLD\RU\A1_MANSION_{name}.TXT'
         for name in ('PART1', 'PART2', 'PART3', 'PART4', 'ROOFARENA')]

def longest(pod, keys):
    lengths = []
    for key in keys:
        for line in pod.read_entry(key).splitlines():
            columns = line.split(b',', 2)
            if len(columns) == 3:
                lengths.append(len(columns[2]))
    return max(lengths)

all_zh, all_ru = longest(chinese, names), longest(original, names)
part4_zh, part4_ru = longest(chinese, names[3:4]), longest(original, names[3:4])
assert (all_zh, all_ru, part4_zh, part4_ru) == (130, 159, 100, 159)
print(f'LENGTHS A1_zh_max={all_zh} A1_ru_max={all_ru} '
      f'part4_zh_max={part4_zh} part4_ru_max={part4_ru} unit=bytes_per_source_field')
