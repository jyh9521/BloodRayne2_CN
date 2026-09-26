from pathlib import Path
from collections import defaultdict
import csv
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / '_cn_project/tools'))
from pod3 import Pod3, Pod3File
from build_missing import parse_line, key_of

def main():
    pod = Pod3.read(HERE / 'payload/LANGUAGE.POD')
    audio = Pod3File(ROOT / 'W32ENSND.POD')
    en = defaultdict(list)
    ru = defaultdict(list)
    for entry in pod.entries:
        if not entry.name.startswith('WORLD\\'):
            continue
        bucket = en if entry.name.startswith('WORLD\\EN\\') else ru if entry.name.startswith('WORLD\\RU\\') else None
        if bucket is None:
            continue
        for line in pod.read_entry(entry.name).splitlines():
            fields, _ = parse_line(line)
            if len(fields) == 3 and key_of(fields).endswith('.wav'):
                bucket[key_of(fields)].append((entry.name, bool(fields[2].strip())))
    out = HERE / 'audio_audit.tsv'
    counts = defaultdict(int)
    with out.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream, delimiter='\t')
        writer.writerow(['audio_name', 'status', 'english_files', 'chinese_files'])
        for entry in audio.entries:
            if not entry.name.lower().endswith('.wav'):
                continue
            key = entry.name.rsplit('\\', 1)[-1].lower()
            e = en[key]
            r = ru[key]
            if e and r and any(has_text for _, has_text in r):
                status = 'script_captioned'
            elif e and r:
                status = 'script_blank_nonverbal_or_review'
            elif e:
                status = 'english_script_missing_chinese'
            else:
                status = 'no_english_script_key_audio_or_unmapped'
            counts[status] += 1
            writer.writerow([entry.name, status, ';'.join(sorted({x for x, _ in e})), ';'.join(sorted({x for x, _ in r}))])
    print('AUDIO_AUDIT ' + ' '.join(f'{k}={v}' for k, v in sorted(counts.items())))

if __name__ == '__main__':
    main()
