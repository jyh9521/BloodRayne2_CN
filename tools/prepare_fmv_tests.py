from pathlib import Path
import json,sys
from build_fmv_full import OUT, ROOT
from build_fmv_probe import cues

BUILD=ROOT/'_cn_project/build/fmv_full_20260925'
BUILD.mkdir(parents=True,exist_ok=True)
widths=[0]*256
for line in (ROOT/'_cn_project/build/full_translation/assets/DATA/GOTHICTITLE_RU.FNT').read_bytes().splitlines():
    if len(line)>2 and line[1:2]==b':':widths[line[0]]=int(line[2:].strip().split(b',')[2])
data=[]
for p in sorted((OUT/'payload/video').glob('*.srt')):
    data.extend(t for _,_,t in cues(p.read_bytes()))
code='static const int kFixtureWidths[256]={'+','.join(map(str,widths))+'};\n'
code+='static const char* kFixtureCues[]={\n'+''.join('    "'+''.join(f'\\x{b:02X}' for b in s)+'",\n' for s in data)+'};\n'
(BUILD/'fixture_data.h').write_text(code,encoding='ascii')
print('FIXTURE_DATA_PASS cues='+str(len(data)))
