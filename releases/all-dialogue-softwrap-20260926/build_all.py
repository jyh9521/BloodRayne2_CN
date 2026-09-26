from pathlib import Path
import hashlib
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / '_cn_project/tools'))
sys.path.insert(0, str(ROOT / '_cn_project/releases/a1-part4-softwrap-20260925'))
from pod3 import Pod3, rebuild_entries
from build_full_translation import carrier_pair
from build_softwrap import softwrap

EXPECTED = '913E8B65727E9EB5146F276F5680E12C4083D122694A25692AA24325947BF8A4'
NAME_RE = re.compile(r'WORLD\\RU\\A[1-4][^\\]*\.TXT\Z')
TAG = re.compile(rb'@@[^@]+@@')

def sha(blob):
    return hashlib.sha256(blob).hexdigest().upper()

def decode(blob, reverse):
    out = []
    pos = 0
    while pos < len(blob):
        if pos + 1 < len(blob) and 0x81 <= blob[pos] <= 0x9F and 0xA1 <= blob[pos+1] <= 0xFE:
            out.append(reverse.get(blob[pos:pos+2], '�'))
            pos += 2
        else:
            out.append(bytes([blob[pos]]).decode('ascii', 'replace'))
            pos += 1
    return ''.join(out)

def main():
    source = Pod3.read(ROOT / 'LANGUAGE.POD')
    assert sha(source.data) == EXPECTED
    mapping = json.loads((ROOT / '_cn_project/releases/fmv-full-20260925/character_map.json').read_text(encoding='utf-8'))
    reverse = {bytes(carrier_pair(index)): char for char, index in mapping.items()}
    punctuation = {bytes(carrier_pair(mapping[ch])) for ch in '，。！？；：、' if ch in mapping}
    replacements = {}
    changed_lines = 0
    diff = ['--- current Chinese story entries', '+++ Chinese story entries with bounded wrap runs']
    for entry in source.entries:
        name = entry.name
        if not NAME_RE.fullmatch(name):
            continue
        original = source.read_entry(name)
        lines = []
        item_changes = []
        for number, line in enumerate(original.splitlines(keepends=True), 1):
            body = line.rstrip(b'\r\n')
            ending = line[len(body):]
            fields = body.split(b',', 2)
            if len(fields) != 3:
                lines.append(line)
                continue
            before = fields[2]
            after = softwrap(before, punctuation)
            assert TAG.findall(before) == TAG.findall(after)
            assert before.replace(b' ', b'') == after.replace(b' ', b'')
            if before != after:
                item_changes.append((number, fields[0].decode('ascii', 'replace'), decode(before, reverse), decode(after, reverse)))
            lines.append(fields[0] + b',' + fields[1] + b',' + after + ending)
        modified = b''.join(lines)
        if modified != original:
            replacements[name] = modified
            changed_lines += len(item_changes)
            diff.append(f'@@ {name} | changed_lines={len(item_changes)} @@')
            for number, key, before, after in item_changes:
                diff.extend([f'@@ line {number} {key} @@', '-' + before, '+' + after])
    assert replacements
    result = Pod3(rebuild_entries(source.data, replacements, {}))
    assert [entry.name for entry in source.entries if source.read_entry(entry.name) != result.read_entry(entry.name)] == list(replacements)
    payload = HERE / 'payload/LANGUAGE.POD'
    payload.parent.mkdir(parents=True, exist_ok=True)
    payload.write_bytes(result.data)
    manifest = {
        'scope': 'WORLD\\RU\\A[1-4]*.TXT, text fields only',
        'before_sha256': sha(source.data),
        'modified_sha256': sha(result.data),
        'changed_entries': len(replacements),
        'changed_lines': changed_lines,
        'unchanged_entries': len(source.entries) - len(replacements),
        'entries': {name: {'before_sha256': sha(source.read_entry(name)), 'after_sha256': sha(blob)} for name, blob in replacements.items()},
    }
    (HERE / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    (HERE / 'DIFF_FILE.diff').write_text('\n'.join(diff) + '\n', encoding='utf-8')
    print(f"BUILD_OK changed_entries={manifest['changed_entries']} changed_lines={changed_lines} other_entries={manifest['unchanged_entries']}_unchanged sha256={manifest['modified_sha256']}")

if __name__ == '__main__':
    main()
