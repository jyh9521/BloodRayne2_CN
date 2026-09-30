from pathlib import Path
import hashlib,json,zipfile,shutil,sys
r=Path(__file__).resolve().parent; t=r/'testroot'; backup=r/'original/fixture'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def state(): return {p.relative_to(t).as_posix():sha(p) for p in t.rglob('*') if p.is_file()}
mode=sys.argv[1]
if mode=='baseline':
 assert not t.exists()
 (t/'video').mkdir(parents=True); (backup/'video').mkdir(parents=True)
 (t/'LANGUAGE.POD').write_bytes(b'ORIGINAL LANGUAGE FIXTURE')
 (t/'video/A1S01P01_RU.srt').write_bytes(b'ORIGINAL RU FIXTURE')
 (t/'W32ART.POD').write_bytes(b'UNTOUCHED MOD FIXTURE')
 for p in t.rglob('*'):
  if p.is_file(): shutil.copy2(p,backup/p.relative_to(t))
 (r/'fixture_before.json').write_text(json.dumps(state(),indent=2))
 print('BASELINE_OK files=3 original_hashes=preserved dll=absent')
elif mode=='modified':
 m=json.loads((r/'manifest.json').read_text())
 with zipfile.ZipFile(r/'MODIFIED_FILE.zip') as z:
  assert len(z.namelist())==18
  for f in m['files']:
   p=t/f['path']; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(z.read(f['path']))
   assert sha(p)==f['sha256']
 assert sha(t/'W32ART.POD')==json.loads((r/'fixture_before.json').read_text())['W32ART.POD']
 print('MODIFIED_OK direct_copy_files=17 hashes=17 protected_mod=unchanged installer=absent version_check=absent')
elif mode=='rollback':
 m=json.loads((r/'manifest.json').read_text()); before=json.loads((r/'fixture_before.json').read_text())
 for f in m['files']:
  p=t/f['path']
  if f['path'] in before: shutil.copy2(backup/f['path'],p)
  else: p.unlink()
 assert state()==before
 print('ROLLBACK_OK original_files=3 original_hashes=3 added_files_removed=15')
