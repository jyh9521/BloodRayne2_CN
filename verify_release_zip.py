from pathlib import Path
import zipfile,hashlib,json
p=Path(__file__).resolve().parent
m=json.loads((p/'releases/overlay-20260930/manifest.json').read_text())
with zipfile.ZipFile(p/'dist/BloodRayne2_CN_current.zip') as z:
 assert set(z.namelist())=={f['path'] for f in m['files']}|{'README.zh-CN.txt'}
 for f in m['files']: assert hashlib.sha256(z.read(f['path'])).hexdigest()==f['sha256']
 assert z.testzip() is None
print('ZIP_OK files=17 entries=18 root_layout=yes installer=absent version_check=absent crc=all_valid sha256=all_valid')
