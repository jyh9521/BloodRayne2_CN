from pathlib import Path
from collections import defaultdict
import csv
import hashlib
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / '_cn_project/tools'))
from pod3 import Pod3, Pod3File
from build_missing import NEW_FILES, TAG, parse_line, key_of

def check(path):
    pod = Pod3.read(path)
    sounds = Pod3File(ROOT / 'W32ENSND.POD')
    names = set(pod.by_name)
    missing_files = []
    missing_keys = []
    tags_bad = []
    long_runs = []
    blank = []
    audio_script_keys = set()
    for entry in pod.entries:
        if not entry.name.startswith('WORLD\\EN\\'):
            continue
        target = entry.name.replace('WORLD\\EN\\', 'WORLD\\RU\\', 1)
        en_lines = pod.read_entry(entry.name).splitlines()
        if target not in names:
            audio = any(len(f := parse_line(x)[0]) == 3 and key_of(f).endswith('.wav') and
                        'SOUND\\' + key_of(f).upper() in sounds.by_name for x in en_lines)
            if audio:
                missing_files.append(target)
            continue
        ru_lines = pod.read_entry(target).splitlines()
        ru = defaultdict(list)
        for line in ru_lines:
            fields, _ = parse_line(line)
            if len(fields) == 3:
                ru[key_of(fields)].append(fields[2])
        for line in en_lines:
            fields, _ = parse_line(line)
            if len(fields) != 3:
                continue
            key = key_of(fields)
            if target.rsplit('\\', 1)[1] in NEW_FILES and key in ru and TAG.findall(fields[2]) != TAG.findall(ru[key][0]):
                tags_bad.append((target, key))
            if not key.endswith('.wav') or 'SOUND\\' + key.upper() not in sounds.by_name:
                continue
            audio_script_keys.add(key)
            if key not in ru:
                missing_keys.append((target, key))
            else:
                for value in ru[key]:
                    if not value.strip():
                        blank.append((target, key))
                    runs = [len(m.group()) for m in re.finditer(rb'\S+', TAG.sub(b' ', value))]
                    if runs and max(runs) > 48:
                        long_runs.append((target, key, max(runs)))
    print(f'entries={len(pod.entries)} scripted_audio_keys={len(audio_script_keys)} missing_files={len(missing_files)} missing_keys={len(missing_keys)} blank_rows={len(blank)} tag_mismatches={len(tags_bad)} long_runs={len(long_runs)}')
    for label, items in [('missing_files', missing_files), ('missing_keys', missing_keys), ('tag_mismatches', tags_bad), ('long_runs', long_runs)]:
        for item in items[:12]:
            print(label, item)
    return len(missing_files), len(missing_keys), len(blank), len(tags_bad), len(long_runs)

if __name__ == '__main__':
    path = Path(sys.argv[1])
    counts = check(path)
    if len(sys.argv) > 2 and sys.argv[2] == '--require-complete':
        assert counts[:2] == (0, 0) and counts[3:] == (0, 0), counts
