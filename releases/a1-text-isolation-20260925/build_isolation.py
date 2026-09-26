from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / '_cn_project' / 'tools'))
from pod3 import Pod3, rebuild_entries

OUT = Path(__file__).resolve().parent
CURRENT = ROOT / 'LANGUAGE.POD'
BASELINE = ROOT / '_cn_project' / 'baseline' / 'LANGUAGE.POD'
NAMES = [
    rf'WORLD\RU\A1_MANSION_{name}.TXT'
    for name in ('PART1', 'PART2', 'PART3', 'PART4', 'ROOFARENA')
]

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()

def main() -> None:
    current = Pod3.read(CURRENT)
    original = Pod3.read(BASELINE)
    assert digest(current.data) == '3D362A472C6BECF2F2F332055831BDFA1139870FD6D4A9190DA5B1274B46BCB5'
    replacements = {name: original.read_entry(name) for name in NAMES}
    result = Pod3(rebuild_entries(current.data, replacements, {}))
    assert not result.verify_crcs()
    changed = [name for name in current.by_name if current.read_entry(name) != result.read_entry(name)]
    assert changed == NAMES or set(changed) == set(NAMES), changed
    assert all(result.read_entry(name) == original.read_entry(name) for name in NAMES)
    out = OUT / 'payload' / 'LANGUAGE.POD'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(result.data)
    rows = [
        {
            'entry': name,
            'before_size': len(current.read_entry(name)),
            'after_size': len(result.read_entry(name)),
            'before_sha256': digest(current.read_entry(name)),
            'after_sha256': digest(result.read_entry(name)),
        }
        for name in NAMES
    ]
    manifest = {
        'before_sha256': digest(current.data),
        'modified_sha256': digest(result.data),
        'baseline_archive_sha256': digest(original.data),
        'changed_entries': rows,
        'unchanged_entries': len(current.entries) - len(rows),
    }
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    lines = ['--- current LANGUAGE.POD', '+++ A1-text-isolation LANGUAGE.POD']
    for row in rows:
        lines += [f"@@ {row['entry']} @@",
                  f"-size={row['before_size']} sha256={row['before_sha256']}",
                  f"+size={row['after_size']} sha256={row['after_sha256']}"]
    (OUT / 'DIFF_FILE.diff').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f"ISOLATION_BUILD_OK changed={len(rows)} unchanged={manifest['unchanged_entries']} "
          f"sha256={manifest['modified_sha256']}")

if __name__ == '__main__':
    main()
