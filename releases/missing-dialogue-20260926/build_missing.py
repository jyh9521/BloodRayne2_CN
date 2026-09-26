from pathlib import Path
from collections import defaultdict
import csv
import hashlib
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / '_cn_project/tools'))
sys.path.insert(0, str(ROOT / '_cn_project/releases/a1-part4-softwrap-20260925'))
from pod3 import Pod3, Pod3File, rebuild_entries
from build_full_translation import encode_text, carrier_pair
from build_softwrap import softwrap

EXPECTED = '1A068F7BA4430B2BA8607B3D81B44F80BFB44E0A95729FBBF8D48F678F01E9A4'
NEW_FILES = ('A1_MANSION_PART2_5.TXT', 'A1_MANSION_PART5.TXT',
             'A2_MEATPACKING.TXT', 'A3_WETWORKS_S_2.TXT')
BLANK_KEYS = {'a1s2_ephemera_5.wav', 'a2s2_rayne_51.wav',
              'a2s4_rayne_22.wav', 'a4s3_kagan_14.wav'}
TAG = re.compile(rb'@@[^@]+@@')

def sha(blob):
    return hashlib.sha256(blob).hexdigest().upper()

def parse_line(line):
    body = line.rstrip(b'\r\n')
    return body.split(b',', 2), line[len(body):]

def key_of(fields):
    return fields[0].strip().decode('cp1251', 'replace').lower()

def main():
    current = Pod3.read(ROOT / 'LANGUAGE.POD')
    assert sha(current.data) == EXPECTED
    sounds = Pod3File(ROOT / 'W32ENSND.POD')
    mapping = json.loads((ROOT / '_cn_project/releases/fmv-full-20260925/character_map.json').read_text(encoding='utf-8'))
    punctuation = {bytes(carrier_pair(mapping[ch])) for ch in '，。！？；：、' if ch in mapping}
    with (HERE / 'new_translations.tsv').open(encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream, dialect='excel-tab'))
    manual = {row['key'].lower(): row['translation_zh'] for row in rows}
    assert len(manual) == len(rows)
    assert all(not {c for c in value if ord(c) > 127 and c not in mapping} for value in manual.values())

    # Every source term present in a newly translated English line must use the glossary rendering.
    with (ROOT / '_cn_project/translation/dialogue_deduplicated/glossary_zh.tsv').open(encoding='utf-8', newline='') as stream:
        glossary = list(csv.DictReader(stream, dialect='excel-tab'))
    en_rows = defaultdict(list)
    for entry in current.entries:
        if not entry.name.startswith('WORLD\\EN\\'):
            continue
        for number, line in enumerate(current.read_entry(entry.name).splitlines(keepends=True), 1):
            fields, ending = parse_line(line)
            if len(fields) == 3:
                en_rows[key_of(fields)].append((entry.name, number, fields, ending))
    for key, target in manual.items():
        matches = en_rows[key]
        if not matches and key not in BLANK_KEYS:
            raise ValueError(f'No English source for {key}')
        for _, _, fields, _ in matches:
            source = fields[2].decode('cp1252', 'replace')
            for term in glossary:
                if re.search(term['match_pattern'], source, re.IGNORECASE) and term['translation_zh'] not in target:
                    raise ValueError(f'Glossary mismatch {key}: {term["source_term"]} -> {term["translation_zh"]}')

    known = defaultdict(list)
    known_global = defaultdict(list)
    for entry in current.entries:
        if not entry.name.startswith('WORLD\\RU\\'):
            continue
        act = entry.name.rsplit('\\', 1)[1][:2]
        for line in current.read_entry(entry.name).splitlines():
            fields, _ = parse_line(line)
            if len(fields) == 3 and fields[2].strip():
                known[(act, key_of(fields))].append(fields[2])
                known_global[key_of(fields)].append(fields[2])

    def translated(act, key):
        if key in manual:
            return softwrap(encode_text(manual[key], mapping), punctuation)
        options = known.get((act, key), []) or known_global.get(key, [])
        if not options:
            raise ValueError(f'No Chinese translation for {act} {key}')
        return options[0]

    replacements = {}
    additions = {}
    new_wav_keys = set()
    for filename in NEW_FILES:
        source_name = f'WORLD\\EN\\{filename}'
        dest_name = f'WORLD\\RU\\{filename}'
        assert dest_name not in current.by_name
        act = filename[:2]
        output = []
        for line in current.read_entry(source_name).splitlines(keepends=True):
            fields, ending = parse_line(line)
            if len(fields) != 3 or not fields[2].strip():
                output.append(line)
                continue
            key = key_of(fields)
            if key.endswith('.wav') or key in manual:
                text = translated(act, key)
            else:
                options = known.get((act, key), []) or known_global.get(key, [])
                text = next((candidate for candidate in options
                             if TAG.findall(candidate) == TAG.findall(fields[2])), fields[2])
            if TAG.findall(text) != TAG.findall(fields[2]):
                raise ValueError(f'Control-tag mismatch: {source_name} {key}')
            output.append(fields[0] + b',' + fields[1] + b',' + text + ending)
            if key.endswith('.wav') and 'SOUND\\' + key.upper() in sounds.by_name:
                new_wav_keys.add(key)
        additions[dest_name] = b''.join(output)

    # Restore records omitted from existing RU level fragments. This covers
    # both monolithic and split meatpacking level-load paths.
    insertion_rows = defaultdict(list)
    for key in (f'a3s3_lminion{x}_{n}.wav' for x, nums in ((1,(1,2,3,4)),(2,(1,2,3,4,5,6,7))) for n in nums):
        insertion_rows['A3_WETWORKS_S_1.TXT'].append(key)
    insertion_rows['A4_PARK_2.TXT'].append('a2s1_civilian_1.wav')
    for key in sorted(k for k in manual if k.startswith('a2_') and k.endswith('.wav')):
        occurrences = en_rows[key]
        assert occurrences
        first_line = min(n for file, n, _, _ in occurrences if file.endswith('A2_MEATPACKING.TXT'))
        target_file = 'A2_MEATPACKING_1.TXT' if first_line <= 19 else 'A2_MEATPACKING_2.TXT'
        insertion_rows[target_file].append(key)

    for filename, keys in insertion_rows.items():
        name = f'WORLD\\RU\\{filename}'
        lines = current.read_entry(name).splitlines(keepends=True)
        present = {key_of(fields) for line in lines if len(fields := parse_line(line)[0]) == 3}
        to_add = []
        for key in keys:
            if key in present:
                continue
            matches = en_rows[key]
            assert matches
            _, _, fields, _ = matches[0]
            text = translated(filename[:2], key)
            to_add.append(fields[0] + b',' + fields[1] + b',' + text + b'\r\n')
        if to_add:
            replacements[name] = b''.join(lines + to_add)

    blank_replacements = defaultdict(list)
    for entry in current.entries:
        if not entry.name.startswith('WORLD\\RU\\'):
            continue
        lines = current.read_entry(entry.name).splitlines(keepends=True)
        output = []
        changed = False
        for line in lines:
            fields, ending = parse_line(line)
            if len(fields) == 3 and key_of(fields) in BLANK_KEYS and not fields[2].strip():
                fields[2] = translated(entry.name.rsplit('\\', 1)[1][:2], key_of(fields))
                line = b','.join(fields) + ending
                changed = True
            output.append(line)
        if changed:
            blank_replacements[entry.name] = b''.join(output)
    for name, blob in blank_replacements.items():
        if name in replacements:
            # Re-apply blank replacements to a file that also received new keys.
            existing = replacements[name]
            old_lines = current.read_entry(name).splitlines(keepends=True)
            new_lines = blob.splitlines(keepends=True)
            assert len(existing.splitlines()) >= len(old_lines) == len(new_lines)
            replacements[name] = b''.join(new_lines) + b''.join(existing.splitlines(keepends=True)[len(old_lines):])
        else:
            replacements[name] = blob

    result = Pod3(rebuild_entries(current.data, replacements, additions))
    payload = HERE / 'payload/LANGUAGE.POD'
    payload.parent.mkdir(parents=True, exist_ok=True)
    payload.write_bytes(result.data)
    manifest = {
        'before_sha256': sha(current.data),
        'modified_sha256': sha(result.data),
        'new_files': sorted(additions),
        'modified_files': sorted(replacements),
        'new_file_existing_audio_keys': len(new_wav_keys),
        'manual_translation_count': len(manual),
        'original_entries_unchanged': 388-len(replacements),
    }
    (HERE / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    diff = ['--- current LANGUAGE.POD', '+++ missing subtitle additions']
    for name, blob in sorted(replacements.items()):
        diff += [f'@@ REPLACE {name} @@', f'-sha256={sha(current.read_entry(name))} size={len(current.read_entry(name))}', f'+sha256={sha(blob)} size={len(blob)}']
    for name, blob in sorted(additions.items()):
        diff += [f'@@ ADD {name} @@', f'+sha256={sha(blob)} size={len(blob)}']
    diff += ['@@ MANUALLY TRANSLATED CAPTION/TEXT KEYS @@']
    for key, translation in sorted(manual.items()):
        diff.append(f'+{key}\t{translation}')
    (HERE / 'DIFF_FILE.diff').write_text('\n'.join(diff) + '\n', encoding='utf-8')
    print(f"BUILD_OK added_files={len(additions)} modified_files={len(replacements)} new_file_audio_keys={len(new_wav_keys)} manual_translations={len(manual)} sha256={sha(result.data)}")

if __name__ == '__main__':
    main()
