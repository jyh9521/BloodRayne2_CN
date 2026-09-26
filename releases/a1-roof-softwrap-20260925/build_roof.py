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

NAME = r'WORLD\RU\A1_MANSION_ROOFARENA.TXT'
CURRENT = ROOT / 'LANGUAGE.POD'
EXPECTED = 'D703A8BA1A6C48C180B6F58F015A9D25678D608DF9326F7FEF332357078F6BA4'

def sha(data):
    return hashlib.sha256(data).hexdigest().upper()

def decoded(blob, reverse):
    out = []
    i = 0
    while i < len(blob):
        if i + 1 < len(blob) and 0x81 <= blob[i] <= 0x9F and 0xA1 <= blob[i+1] <= 0xFE:
            out.append(reverse.get(blob[i:i+2], '�'))
            i += 2
        else:
            out.append(bytes([blob[i]]).decode('ascii', 'replace'))
            i += 1
    return ''.join(out)

def main():
    source = Pod3.read(CURRENT)
    assert sha(source.data) == EXPECTED
    original = source.read_entry(NAME)
    mapping = json.loads((ROOT / '_cn_project/releases/fmv-full-20260925/character_map.json').read_text(encoding='utf-8'))
    reverse = {bytes(carrier_pair(value)): char for char, value in mapping.items()}
    punctuation = {bytes(carrier_pair(mapping[ch])) for ch in '，。！？；：、' if ch in mapping}
    lines = []
    changes = []
    for number, line in enumerate(original.splitlines(keepends=True), 1):
        body = line.rstrip(b'\r\n')
        ending = line[len(body):]
        fields = body.split(b',', 2)
        if len(fields) != 3:
            lines.append(line)
            continue
        after = softwrap(fields[2], punctuation)
        assert after.replace(b' ', b'') == fields[2].replace(b' ', b'')
        if after != fields[2]:
            changes.append((number, fields[0].decode('ascii', 'replace'), decoded(fields[2], reverse), decoded(after, reverse)))
        lines.append(fields[0] + b',' + fields[1] + b',' + after + ending)
    modified = b''.join(lines)
    result = Pod3(rebuild_entries(source.data, {NAME: modified}, {}))
    assert not result.verify_crcs()
    assert [e.name for e in source.entries if source.read_entry(e.name) != result.read_entry(e.name)] == [NAME]
    assert changes
    payload = HERE / 'payload/LANGUAGE.POD'
    payload.parent.mkdir(parents=True, exist_ok=True)
    payload.write_bytes(result.data)
    (HERE / 'manifest.json').write_text(json.dumps({
        'entry': NAME,
        'before_sha256': sha(source.data),
        'modified_sha256': sha(result.data),
        'entry_before_sha256': sha(original),
        'entry_after_sha256': sha(modified),
        'changed_lines': len(changes),
        'unchanged_entries': 387,
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    diff = ['--- ROOFARENA Chinese', '+++ ROOFARENA Chinese with wrap opportunities']
    for number, key, before, after in changes:
        diff += [f'@@ line {number} {key} @@', '-' + before, '+' + after]
    (HERE / 'DIFF_FILE.diff').write_text('\n'.join(diff) + '\n', encoding='utf-8')
    print(f'ROOF_BUILD_OK changed_lines={len(changes)} other_entries=387_unchanged sha256={sha(result.data)}')

if __name__ == '__main__':
    main()
