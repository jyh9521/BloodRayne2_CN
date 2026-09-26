"""Read SFNT Unicode cmap formats 4/12 without external font packages."""
from pathlib import Path
import struct,csv

ROOT=Path(__file__).resolve().parents[2]
data=Path('C:/Windows/Fonts/NotoSansSC-VF.ttf').read_bytes()
u16=lambda o: struct.unpack_from('>H',data,o)[0]
u32=lambda o: struct.unpack_from('>I',data,o)[0]
tables={data[12+i*16:16+i*16]:u32(20+i*16) for i in range(u16(4))}
cmap=tables[b'cmap']
subtables=[]
for i in range(u16(cmap+2)):
    o=cmap+4+i*8; platform,encoding=struct.unpack_from('>HH',data,o)
    if platform==0 or (platform==3 and encoding in (1,10)):
        sub=cmap+u32(o+4)
        if u16(sub) in (4,12): subtables.append(sub)
assert subtables

def glyph(cp):
    for sub in subtables:
        if u16(sub)==12:
            for i in range(u32(sub+12)):
                a,b,g=struct.unpack_from('>III',data,sub+16+12*i)
                if a<=cp<=b and g+cp-a: return g+cp-a
        elif cp<=65535:
            n=u16(sub+6)//2; end=sub+14; start=end+2*n+2; delta=start+2*n; offset=delta+2*n
            for i in range(n):
                if u16(start+2*i)<=cp<=u16(end+2*i):
                    shift=u16(delta+2*i); ro=u16(offset+2*i)
                    g=u16(offset+2*i+ro+2*(cp-u16(start+2*i))) if ro else cp
                    if ro and not g: continue
                    g=(g+shift)&65535
                    if g: return g
    return 0

with (ROOT/'_cn_project/build/full_translation/character_map.tsv').open(encoding='utf-8-sig',newline='') as f:
    rows=list(csv.DictReader(f,delimiter='\t'))
missing=[r['unicode'] for r in rows if not glyph(ord(r['character']))]
assert not missing,missing
assert not glyph(0x10FFFF)
print(f'FONT_COVERAGE_PASS glyphs={len(rows)} missing=0 negative_control=PASS')
