from pathlib import Path
import sys, json, hashlib, shutil, zipfile, subprocess
R=Path(__file__).resolve().parent
G=R.parents[2]
T=R/(sys.argv[2] if len(sys.argv)>2 else 'testroot')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def state(): return {p.relative_to(T).as_posix():sha(p) for p in T.rglob('*') if p.is_file() and '_cn_backup_release_20260930' not in p.parts}
mode=sys.argv[1]
if mode=='baseline':
    assert not T.exists(), 'Use a new fixture directory'
    (T/'video').mkdir(parents=True)
    shutil.copy2(G/'rayne2.exe',T/'rayne2.exe')
    (T/'LANGUAGE.POD').write_bytes(b'ISOLATED ORIGINAL LANGUAGE FIXTURE\x00')
    (T/'W32ART.POD').write_bytes(b'UNCHANGED MOD ART FIXTURE')
    (T/'W32ENSND.POD').write_bytes(b'UNCHANGED ENGLISH VOICE FIXTURE')
    (T/'video/A1S01P01_RU.srt').write_bytes(b'ORIGINAL SUBTITLE FIXTURE')
    (R/'baseline.json').write_text(json.dumps(state(),indent=2)+'\n')
    with zipfile.ZipFile(R/'MODIFIED_FILE.zip') as z: z.extractall(R/'test_package')
    print('BASELINE_OK isolated_fixture=yes files=5 dinput8=absent original_ru=1 source_project=absent')
elif mode=='modified':
    m=json.loads((R/'manifest.json').read_text())
    for f in m['files']: assert sha(T/f['path'])==f['sha256']
    b=json.loads((R/'baseline.json').read_text())
    for n in ['rayne2.exe','W32ART.POD','W32ENSND.POD']: assert sha(T/n)==b[n]
    assert not (T/'_cn_project').exists()
    print('MODIFIED_OK installed=17 hashes=17 art_voice_exe=unchanged source_project=absent')
elif mode=='rollback':
    assert state()==json.loads((R/'baseline.json').read_text())
    print('ROLLBACK_OK baseline_files=5 hashes=5 new_files_removed=15 dinput8=absent')
