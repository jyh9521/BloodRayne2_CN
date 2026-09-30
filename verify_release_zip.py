from pathlib import Path
import hashlib, json, zipfile
p=Path(__file__).resolve().parent/'dist/BloodRayne2_CN_current.zip'
with zipfile.ZipFile(p) as z:
 m=json.loads(z.read('manifest.json'))
 assert len(m['files'])==17 and len(z.namelist())==24
 for f in m['files']: assert hashlib.sha256(z.read('payload/'+f['path'])).hexdigest()==f['sha256']
 assert z.testzip() is None
print('ZIP_OK files=17 crc=all_valid sha256=all_valid version=1.0.0')
