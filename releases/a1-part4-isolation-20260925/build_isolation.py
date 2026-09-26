from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / '_cn_project' / 'tools'))
from pod3 import Pod3, rebuild_entries

OUT = Path(__file__).resolve().parent
CURRENT = ROOT / 'LANGUAGE.POD'
CHINESE = ROOT / '_cn_project' / 'test_backup' / 'a1_text_isolation_20260925' / 'LANGUAGE.POD'
RESTORE = [
    rf'WORLD\RU\A1_MANSION_{name}.TXT'
    for name in ('PART1', 'PART2', 'PART3', 'ROOFARENA')
]
KEEP_ORIGINAL = r'WORLD\RU\A1_MANSION_PART4.TXT'

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()

def main() -> None:
    current = Pod3.read(CURRENT)
    chinese = Pod3.read(CHINESE)
    assert sha(current.data) == '92199661B9E3E07C98A216269B2BFA629433073268CE9620539156B7EF26C9A9'
    replacements = {name: chinese.read_entry(name) for name in RESTORE}
    result = Pod3(rebuild_entries(current.data, replacements, {}))
    assert not result.verify_crcs()
    changed = [entry.name for entry in current.entries
               if current.read_entry(entry.name) != result.read_entry(entry.name)]
    assert set(changed) == set(RESTORE)
    assert result.read_entry(KEEP_ORIGINAL) == current.read_entry(KEEP_ORIGINAL)
    out = OUT / 'payload' / 'LANGUAGE.POD'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(result.data)
    manifest = {
        'before_sha256': sha(current.data),
        'modified_sha256': sha(result.data),
        'restored_chinese_entries': RESTORE,
        'kept_original_entry': KEEP_ORIGINAL,
        'unchanged_entries': len(current.entries) - len(RESTORE),
    }
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    lines = ['--- A1-all-original LANGUAGE.POD', '+++ A1-part4-original-only LANGUAGE.POD']
    for name in RESTORE:
        before = current.read_entry(name)
        after = result.read_entry(name)
        lines.extend([f'@@ {name} @@',
                      f'-size={len(before)} sha256={sha(before)}',
                      f'+size={len(after)} sha256={sha(after)}'])
    lines.append(f'UNCHANGED {KEEP_ORIGINAL}')
    (OUT / 'DIFF_FILE.diff').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f"PART4_ISOLATION_BUILD_OK restored_chinese=4 kept_original=1 "
          f"other_unchanged={manifest['unchanged_entries']} sha256={manifest['modified_sha256']}")

if __name__ == '__main__':
    main()
