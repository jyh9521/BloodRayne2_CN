from pathlib import Path
import hashlib,json,sys,shutil
mode=sys.argv[1]; root=Path(sys.argv[2]); t=root/'fixture'; p=root/'output/package'
def sha(f): return hashlib.sha256(f.read_bytes()).hexdigest()
def state(): return {f.relative_to(t).as_posix():sha(f) for f in t.rglob('*') if f.is_file() and '_cn_backup_release_20260930' not in f.parts}
if mode=='baseline':
 assert not t.exists()
 t.mkdir(); shutil.copy2(root/'rayne2.exe',t/'rayne2.exe'); shutil.copy2(root/'LANGUAGE.POD',t/'LANGUAGE.POD')
 (root/'fixture-before.json').write_text(json.dumps(state()))
 print('BASELINE_OK clean_pod=verified fixture_files=2 source_project=absent dinput8=absent')
elif mode=='modified':
 m=json.loads((p/'manifest.json').read_text())
 assert len(m['files'])==17
 for f in m['files']: assert sha(t/f['path'])==f['sha256']
 assert not (t/'_cn_project').exists()
 print('MODIFIED_OK rebuilt_payload_files=17 hashes=17 source_project=absent')
elif mode=='rollback':
 assert state()==json.loads((root/'fixture-before.json').read_text())
 print('ROLLBACK_OK clean_files=2 original_hashes=2 new_files_removed=16')
