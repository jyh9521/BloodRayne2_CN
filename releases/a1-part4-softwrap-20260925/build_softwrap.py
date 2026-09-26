from pathlib import Path
import csv
import hashlib
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / '_cn_project' / 'tools'))
from pod3 import Pod3, rebuild_entries
from build_full_translation import carrier_pair

HERE = Path(__file__).resolve().parent
CURRENT = ROOT / 'LANGUAGE.POD'
CHINESE = ROOT / '_cn_project/test_backup/a1_text_isolation_20260925/LANGUAGE.POD'
NAME = r'WORLD\RU\A1_MANSION_PART4.TXT'
MAX_RUN = 48
TAG = re.compile(rb'@@[^@]+@@')

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()

def units(blob: bytes) -> list[bytes]:
    result = []
    at = 0
    while at < len(blob):
        if (0x81 <= blob[at] <= 0x9F and at + 1 < len(blob)
                and 0xA1 <= blob[at + 1] <= 0xFE):
            result.append(blob[at:at + 2])
            at += 2
        else:
            result.append(blob[at:at + 1])
            at += 1
    return result

def wrap_run(blob: bytes, punctuation: set[bytes]) -> bytes:
    if len(blob) <= MAX_RUN:
        return blob
    letters = units(blob)
    output = []
    start = 0
    while start < len(letters):
        size = 0
        end = start
        preferred = None
        while end < len(letters) and size + len(letters[end]) <= MAX_RUN:
            size += len(letters[end])
            end += 1
            if letters[end - 1] in punctuation:
                preferred = end
        if end == len(letters):
            output.extend(letters[start:])
            break
        if preferred is not None and preferred > start + 4:
            end = preferred
        assert end > start
        output.extend(letters[start:end])
        output.append(b' ')
        start = end
    return b''.join(output)

def softwrap(text: bytes, punctuation: set[bytes]) -> bytes:
    # Keep every @@...@@ control tag byte-for-byte; only text between tags changes.
    result = []
    at = 0
    for match in TAG.finditer(text):
        result.append(re.sub(rb'\S+', lambda m: wrap_run(m.group(), punctuation),
                             text[at:match.start()]))
        result.append(match.group())
        at = match.end()
    result.append(re.sub(rb'\S+', lambda m: wrap_run(m.group(), punctuation),
                         text[at:]))
    return b''.join(result)

def main() -> None:
    current = Pod3.read(CURRENT)
    full = Pod3.read(CHINESE)
    assert sha(current.data) == '3B9A1D0F9BAA338FFE739B27B05AA6FB87D07E17DCDEE15A0CEE55AF1C0319BC'
    old_lines = full.read_entry(NAME).splitlines(keepends=True)
    map_path = ROOT / '_cn_project/releases/fmv-full-20260925/character_map.json'
    mapping = json.loads(map_path.read_text(encoding='utf-8'))
    punctuation = {bytes(carrier_pair(mapping[ch])) for ch in '，。！？；：、' if ch in mapping}
    output = []
    changes = []
    for number, line in enumerate(old_lines, 1):
        body = line.rstrip(b'\r\n')
        ending = line[len(body):]
        columns = body.split(b',', 2)
        if len(columns) != 3:
            output.append(line)
            continue
        before = columns[2]
        after = softwrap(before, punctuation)
        assert TAG.findall(before) == TAG.findall(after)
        assert after.replace(b' ', b'') == before.replace(b' ', b'')
        if after != before:
            changes.append((number, columns[0].decode('cp1251', 'replace'),
                            len(before), len(after)))
        output.append(columns[0] + b',' + columns[1] + b',' + after + ending)
    modified = b''.join(output)
    result = Pod3(rebuild_entries(current.data, {NAME: modified}, {}))
    assert not result.verify_crcs()
    assert [e.name for e in current.entries
            if current.read_entry(e.name) != result.read_entry(e.name)] == [NAME]
    assert len(changes) > 0
    payload = HERE / 'payload/LANGUAGE.POD'
    payload.parent.mkdir(parents=True, exist_ok=True)
    payload.write_bytes(result.data)
    (HERE / 'modified_part4.bin').write_bytes(modified)
    (HERE / 'changes.tsv').write_text(
        'line\tkey\tbefore_bytes\tafter_bytes\n' +
        ''.join(f'{n}\t{k}\t{a}\t{b}\n' for n, k, a, b in changes),
        encoding='utf-8')
    (HERE / 'manifest.json').write_text(json.dumps({
        'before_sha256': sha(current.data),
        'modified_sha256': sha(result.data),
        'entry': NAME,
        'max_unbroken_text_run_bytes': MAX_RUN,
        'changed_lines': len(changes),
        'entry_before_sha256': sha(current.read_entry(NAME)),
        'entry_after_sha256': sha(modified),
    }, indent=2), encoding='utf-8')
    (HERE / 'DIFF_FILE.diff').write_text(
        f'--- {NAME} original Russian\n+++ {NAME} Chinese soft-wrap\n'
        f'@@ single POD entry; {len(changes)} lines gained ASCII wrap spaces; all tags preserved @@\n'
        f'-size={len(current.read_entry(NAME))} sha256={sha(current.read_entry(NAME))}\n'
        f'+size={len(modified)} sha256={sha(modified)}\n', encoding='utf-8')
    print(f'SOFTWRAP_BUILD_OK entry=PART4 changed_lines={len(changes)} '
          f'max_run={MAX_RUN} unchanged_entries=387 sha256={sha(result.data)}')

if __name__ == '__main__':
    main()
