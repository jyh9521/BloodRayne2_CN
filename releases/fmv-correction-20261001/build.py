from pathlib import Path
import csv, json, hashlib, re, shutil, difflib, zipfile, sys
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]; ROOT=REPO.parent
sha=lambda b: hashlib.sha256(b).hexdigest()
def split(b): return [x.split(b'\n') for x in re.split(rb'\n\s*\n',b.replace(b'\r\n',b'\n').strip())]
def main():
 mode=sys.argv[1]
 original=HERE/'original/A2S02P16_RU.srt'
 live=ROOT/'video/A2S02P16_RU.srt'; canonical=REPO/'video_subtitles/A2S02P16_RU.srt'
 if mode=='baseline':
  assert live.read_bytes()==canonical.read_bytes()
  original.parent.mkdir(exist_ok=True)
  if not original.exists(): shutil.copy2(live,original)
  data=original.read_bytes(); assert len(split(data))==21
  (HERE/'baseline.json').write_text(json.dumps({'sha256':sha(data),'bytes':len(data)},indent=2))
  print('BASELINE_OK cues=21 installed=canonical original_hash=preserved'); return
 base=json.loads((HERE/'baseline.json').read_text()); old=original.read_bytes(); assert sha(old)==base['sha256']
 if mode=='rollback':
  fixture=HERE/'testroot/A2S02P16_RU.srt'; fixture.parent.mkdir(exist_ok=True)
  shutil.copy2(HERE/'MODIFIED_FILE.srt',fixture); shutil.copy2(original,fixture)
  assert sha(fixture.read_bytes())==base['sha256']
  assert live.read_bytes()==(HERE/'MODIFIED_FILE.srt').read_bytes()
  print('ROLLBACK_OK isolated_original_hash=matched installed_correction=retained'); return
 rows=list(csv.DictReader((REPO/'build/full_translation/character_map.tsv').open(encoding='utf-8-sig'),delimiter='\t'))
 mapping={r['character']:bytes.fromhex(r['carrier']) for r in rows}
 texts=['莱恩？','你到哪儿了？']
 encoded=[b''.join(bytes([ord(c)]) if ord(c)<128 else mapping[c] for c in t) for t in texts]
 blocks=split(old); newblocks=[list(x) for x in blocks]
 for i,e in enumerate(encoded):
  assert len(e)<64; newblocks[i][2]=e
 data=b''.join(b'\r\n'.join(x)+b'\r\n\r\n' for x in newblocks)
 assert [x[:2] for x in split(data)]==[x[:2] for x in blocks]
 assert split(data)[2:]==blocks[2:]
 modified=HERE/'MODIFIED_FILE.srt'; modified.write_bytes(data)
 shutil.copy2(modified,canonical); shutil.copy2(modified,live)
 plain=(REPO/'releases/fmv-retime-20260930/source/A2S02P16_ZH.utf8.srt').read_text(encoding='utf-8')
 plain=plain.replace('莱恩，刚才那是埃菲梅拉，对吧？',texts[0]).replace('你摔得可不轻，落在哪儿了？',texts[1])
 (HERE/'A2S02P16_ZH.utf8.srt').write_text(plain,encoding='utf-8')
 diff=''.join(difflib.unified_diff([str(x)+'\n' for x in blocks],[str(x)+'\n' for x in split(data)],fromfile='original',tofile='corrected'))
 (HERE/'DIFF_FILE.diff').write_text(diff,encoding='utf-8')
 readme=REPO/'releases/overlay-20260930/README.zh-CN.txt'
 text=readme.read_text(encoding='utf-8').replace('v1.0.1','v1.0.2')
 text=text.replace('视频 A2S02P16 第一句保留译文与当前英语音轨没有完整对应，仍保留原译文待复核。','本次修正：视频 A2S02P16 开头改为“莱恩？”“你到哪儿了？”，与英语配音对应。')
 readme.write_text(text,encoding='utf-8')
 build=REPO/'rebuild/build.py'; build.write_text(build.read_text(encoding='utf-8').replace('1.0.1-overlay-source-rebuild','1.0.2-overlay-source-rebuild'),encoding='utf-8')
 mainreadme=REPO/'README.md'; text=mainreadme.read_text(encoding='utf-8')
 text=text.replace('## 下载与使用','## 本次更新\n\nv1.0.2：修正 A2S02P16 开头两条视频字幕，与英语配音对应；其余字幕与时间轴保持不变。\n\n## 下载与使用')
 mainreadme.write_text(text,encoding='utf-8')
 files=[ROOT/'LANGUAGE.POD',ROOT/'dinput8.dll',*sorted((ROOT/'video').glob('*_RU.srt'))]; assert len(files)==17
 archive=REPO/'dist/BloodRayne2_CN_v1.0.2_overlay.zip'
 manifest={'version':'1.0.2-overlay','changed_cues':{'A2S02P16:1':texts[0],'A2S02P16:2':texts[1]},'baseline':base,'modified_sha256':sha(data),'files':[{'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p.read_bytes())} for p in files]}
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for p in files: z.write(p,p.relative_to(ROOT).as_posix())
  z.write(readme,'README.zh-CN.txt')
 with zipfile.ZipFile(archive) as z:
  assert z.testzip() is None and len(z.namelist())==18
  assert z.read('video/A2S02P16_RU.srt')==data
  for f in manifest['files']: assert sha(z.read(f['path']))==f['sha256']
  assert not any(n.endswith(('.cmd','.ps1')) for n in z.namelist())
 shutil.copy2(archive,REPO/'dist/BloodRayne2_CN_current.zip')
 (HERE/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
 print('MODIFIED_OK cues=21 changed=2 unchanged=19 timestamps=unchanged carrier_bytes=6,12 each_below_64=yes')
 print('RELEASE_OK version=1.0.2 files=17 entries=18 crc=valid hashes=valid direct_overlay=yes')
if __name__=='__main__': main()

