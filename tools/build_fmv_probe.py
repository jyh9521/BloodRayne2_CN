"""Build a six-cue FMV probe against the existing v12 atlas; never install it."""
from pathlib import Path
import csv
import difflib
import hashlib
import json
import re
import shutil

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / '_cn_project/releases/fmv-probe-20260923'
VIDEO = ROOT / 'video/A1S01P01_RU.srt'
TEXTS = [
    '准备好了吗？ 你今晚怎么这么安静？',
    '别担心。 有我帮你呢。',
    '我不担心，塞弗林。 我不需要你帮忙， 更不需要硫磺会。',
    '好吧， 至少有我陪着你嘛。',
    '是啊。 今晚恐怕会有不少人死得很惨。',
    '嗯…… 我看有几个会死在你这身裙子上。',
]

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()

def cues(blob):
    result = []
    normalized = blob.replace(b'\r\n', b'\n')
    for block in re.split(rb'\n\s*\n', normalized.strip()):
        lines = block.split(b'\n')
        if len(lines) != 3 or not lines[0].isdigit():
            raise ValueError('Expected numbered, single-text-line SRT cues')
        if not re.fullmatch(rb'\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}', lines[1]):
            raise ValueError('Invalid timestamp syntax')
        result.append(lines)
    return result

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    original = OUT / 'original/A1S01P01_RU.srt'
    original.parent.mkdir(exist_ok=True)
    if not original.exists():
        shutil.copy2(VIDEO, original)
    elif sha(VIDEO) != sha(original):
        raise ValueError('User SRT changed since snapshot; preserve it and use a new release directory')
    rows = list(csv.DictReader((ROOT / '_cn_project/build/full_translation/character_map.tsv').open(encoding='utf-8-sig'), delimiter='\t'))
    mapping = {r['character']: bytes.fromhex(r['carrier']) for r in rows}
    source = cues(original.read_bytes())
    assert len(source) == len(TEXTS) == 6
    editable, compiled = [], []
    for (number, timestamp, _), text in zip(source, TEXTS):
        encoded = b''.join(bytes([ord(c)]) if ord(c) < 128 else mapping[c] for c in text)
        # The stock FMV layout uses 64-byte rows. Keep this first probe below
        # that limit even before automatic wrapping; do not split any pair.
        assert len(encoded) < 64
        head = number + b'\r\n' + timestamp + b'\r\n'
        editable.append(head + text.encode('utf-8') + b'\r\n\r\n')
        compiled.append(head + encoded + b'\r\n\r\n')
    (OUT / 'source').mkdir(exist_ok=True)
    (OUT / 'source/A1S01P01_ZH.utf8.srt').write_bytes(b''.join(editable))
    target = OUT / 'payload/video/A1S01P01_RU.srt'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b''.join(compiled))
    manifest = {
        'build_id': 'fmv-probe-v12-20260923',
        'target': 'video/A1S01P01_RU.srt',
        'payload_sha256': sha(target),
        'original_sha256': sha(original),
        'required_files': {n: sha(ROOT / n) for n in ['LANGUAGE.POD', 'dinput8.dll', 'rayne2.exe']},
        'character_map_sha256': sha(ROOT / '_cn_project/build/full_translation/character_map.tsv'),
        'cues': 6,
        'encoding': 'v12 custom two-byte atlas carrier (not UTF-8/GBK)',
        'timing_source': 'User A1S01P01_RU.srt; all six timestamps preserved byte-for-byte',
        'translation_source': 'Bundled A1S01P01_FR.srt, checked with IT; existing project glossary',
        'installed_before': {n: sha(ROOT / n) for n in ['LANGUAGE.POD', 'dinput8.dll', 'rayne2.exe', 'W32ART.POD', 'W32ENSND.POD', 'video/A1S01P01_RU.srt']},
    }
    # Never silently target a different atlas or DLL build.
    assert manifest['required_files']['LANGUAGE.POD'] == '5CF475C4E80F3245ABA654870DDEF5F2BABF6A4805537C521B01CAC44B9EE577'
    assert manifest['required_files']['dinput8.dll'] == '91326E4B91662C0ABE4DD8628CA7CBFBC19637154A717724DBEF353CFC51FC43'
    (OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    # Hex diff is intentional: deployed text is a binary carrier, not Unicode.
    old = [f'{i+1} {t.decode("ascii")}\n{text.hex(" ")}\n' for i, (_, t, text) in enumerate(source)]
    new = [f'{i+1} {t.decode("ascii")}\n{text.hex(" ")}\n' for i, (_, t, text) in enumerate(cues(target.read_bytes()))]
    (OUT / 'DIFF_FILE.diff').write_text(''.join(difflib.unified_diff(old, new, fromfile='original/A1S01P01_RU.srt', tofile='payload/video/A1S01P01_RU.srt')), encoding='utf-8')
    print('BUILD_PASS cues=6 timestamps=unchanged existing_atlas=yes game_files_written=0')

if __name__ == '__main__':
    main()
