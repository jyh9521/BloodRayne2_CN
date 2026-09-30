from pathlib import Path
import hashlib,json,sys,zipfile,shutil
r=Path(__file__).resolve().parent; p=r.parents[1]; m=json.loads((r/'baseline.json').read_text())
def sha(f): return hashlib.sha256(f.read_bytes()).hexdigest()
mode=sys.argv[1]
if mode=='baseline':
 assert sha(r/'original/README.md')==m['README_before_sha256']
 assert sha(p/'dist/BloodRayne2_CN_current.zip')==m['package_sha256']
 print('BASELINE_OK readme_original_hash=preserved overlay_package=unchanged')
elif mode=='modified':
 s=(p/'README.md').read_text(encoding='utf-8')
 assert (r/'MODIFIED_FILE.md').read_text(encoding='utf-8')==s
 assert len(s)<2600 and 'BUILDING.md' in s and 'INSTALL.cmd' not in s and '权威输入' not in s
 assert (p/'BUILDING.md').exists()
 assert sha(p/'dist/BloodRayne2_CN_current.zip')==m['package_sha256']
 with zipfile.ZipFile(p/'dist/BloodRayne2_CN_current.zip') as z:
  assert len(z.namelist())==18 and 'LANGUAGE.POD' in z.namelist() and not any(n.endswith(('.cmd','.ps1')) for n in z.namelist())
  assert z.testzip() is None
 print('MODIFIED_OK player_readme=yes build_guide=separate overlay_package=unchanged crc=all_valid')
elif mode=='rollback':
 shutil.copy2(r/'original/README.md',r/'fixture_README.md')
 assert sha(r/'fixture_README.md')==m['README_before_sha256']
 print('ROLLBACK_OK isolated_readme=restored original_hash=matched live_readme=retained')
