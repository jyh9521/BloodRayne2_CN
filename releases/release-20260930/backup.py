from pathlib import Path
import hashlib,json,zipfile,shutil,subprocess
R=Path(__file__).resolve().parent
PROJECT=R.parents[1]
ROOT=PROJECT.parent
DEST=Path.home()/'Documents/BloodRayne2_CN_Release_Backup_20260930'
DEST.mkdir(exist_ok=False)
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as s:
  for b in iter(lambda:s.read(1024*1024),b''): h.update(b)
 return h.hexdigest()
shutil.copy2(PROJECT/'dist/BloodRayne2_CN_v1.0.0_20260930.zip',DEST/'BloodRayne2_CN_v1.0.0_20260930.zip')
inputs=[]
for base,prefix in [(PROJECT,'game/_cn_project'),(ROOT/'ART','game/ART'),(Path.home()/'Documents/BloodRayne2','user/Documents/BloodRayne2')]:
 for p in sorted(base.rglob('*')):
  if p.is_file(): inputs.append((p,prefix+'/'+p.relative_to(base).as_posix()))
inputs += [(p,'game/'+p.name) for p in sorted(ROOT.iterdir()) if p.is_file()]
inputs += [(p,'game/video/'+p.name) for p in sorted((ROOT/'video').glob('*.srt'))]
records=[]
archive=DEST/'PROJECT_MODS_SAVES_BACKUP.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as z:
 for i,(p,name) in enumerate(inputs):
  before=p.stat()
  h=hashlib.sha256()
  with p.open('rb') as src,z.open(name,'w',force_zip64=True) as dst:
   for b in iter(lambda:src.read(1024*1024),b''): h.update(b); dst.write(b)
  assert before.st_size==p.stat().st_size and before.st_mtime_ns==p.stat().st_mtime_ns, str(p)
  records.append({'path':name,'bytes':before.st_size,'sha256':h.hexdigest()})
  if i%100==0: print('BACKUP_PROGRESS',i,'of',len(inputs),flush=True)
 z.writestr('BACKUP_MANIFEST.json',json.dumps(records,ensure_ascii=False,indent=2))
with zipfile.ZipFile(archive) as z:
 for f in records:
  h=hashlib.sha256()
  with z.open(f['path']) as s:
   for b in iter(lambda:s.read(1024*1024),b''): h.update(b)
  assert h.hexdigest()==f['sha256'],f['path']
(DEST/'BACKUP_MANIFEST.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
sums='\n'.join(digest(p)+'  '+p.name for p in [archive,DEST/'BloodRayne2_CN_v1.0.0_20260930.zip'])+'\n'
(DEST/'SHA256SUMS.txt').write_text(sums,encoding='ascii')
result=f'BACKUP_OK files={len(records)} bytes={sum(f["bytes"] for f in records)} hashes=all_valid crc=all_valid'
(DEST/'BACKUP_VERIFICATION.txt').write_text(result+'\nOriginal files retained; no cleanup, move, Steam reinstall or game launch performed.\nOriginal BIK videos and Legacy Version not included; reinstall these through Steam.\n',encoding='utf-8')
(DEST/'移走前请读.txt').write_text('请把整个本目录移到游戏目录外的目标磁盘后，再清空测试环境。\nBloodRayne2_CN_v1.0.0_20260930.zip 是玩家用安装包。\nPROJECT_MODS_SAVES_BACKUP.zip 是开发/恢复备份，包含全部 _cn_project（含 .git、历史原文件、源代码和构建证据）、游戏根目录文件、ART 松散模组、全部 SRT、Documents/BloodRayne2 存档与设置。\n这份开发备份不能解压进干净安装后再测试，否则会恢复模组和旧环境。仅使用玩家安装包做新安装测试。\n原 BIK 视频及 Legacy Version 可由 Steam 重装，未放入备份。\nSteam Cloud 可能同步旧存档与设置；如需纯新玩家体验，请自行暂时关闭该游戏云同步，并把已备份的 Documents/BloodRayne2 移走。\n',encoding='utf-8-sig')
print(result,flush=True)
print('BACKUP_DEST '+str(DEST),flush=True)
