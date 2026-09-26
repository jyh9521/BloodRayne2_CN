from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / '_cn_project' / 'tools'))
from pod3 import Pod3

name = r'WORLD\RU\A1_MANSION_PART4.TXT'
zh = Pod3.read(ROOT / '_cn_project/test_backup/a1_text_isolation_20260925/LANGUAGE.POD')
ru = Pod3.read(ROOT / '_cn_project/baseline/LANGUAGE.POD')

def maximum(pod):
    return max(len(run)
               for line in pod.read_entry(name).splitlines()
               for columns in [line.split(b',', 2)] if len(columns) == 3
               for run in re.split(rb'\s+', columns[2]))

zh_max, ru_max = maximum(zh), maximum(ru)
assert (zh_max, ru_max) == (100, 47)
print(f'RUNS part4_chinese_max={zh_max} part4_original_russian_max={ru_max} unit=bytes_without_ASCII_space')
