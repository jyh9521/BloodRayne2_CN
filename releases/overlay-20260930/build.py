from pathlib import Path
import hashlib,json,shutil,zipfile
HERE=Path(__file__).resolve().parent
PROJECT=HERE.parents[1]
ROOT=PROJECT.parent
files=[ROOT/'LANGUAGE.POD',ROOT/'dinput8.dll',*sorted((ROOT/'video').glob('*_RU.srt'))]
assert len(files)==17
manifest={'version':'1.0.1-overlay','files':[{'path':p.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]}
(HERE/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
archive=PROJECT/'dist/BloodRayne2_CN_v1.0.1_overlay.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for p in files: z.write(p,p.relative_to(ROOT).as_posix())
 z.write(HERE/'README.zh-CN.txt','README.zh-CN.txt')
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for f in manifest['files']: assert hashlib.sha256(z.read(f['path'])).hexdigest()==f['sha256']
shutil.copy2(archive,PROJECT/'dist/BloodRayne2_CN_current.zip')
shutil.copy2(archive,HERE/'MODIFIED_FILE.zip')
print('RELEASE_OK files=17 entries=18 root_layout=yes installer=absent version_check=absent hashes=all_valid')
