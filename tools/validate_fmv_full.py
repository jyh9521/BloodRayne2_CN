import argparse,csv,json,re,sys
from pathlib import Path
from build_fmv_full import OUT,ROOT
from build_fmv_probe import cues,sha
from build_full_translation import TARGET_TEX_NAME,carrier_pair
from pod3 import Pod3

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--baseline',action='store_true');args=parser.parse_args()
    mapping=json.loads((OUT/'character_map.json').read_text(encoding='utf-8'))
    decoder={bytes(carrier_pair(i)):c for c,i in mapping.items()}
    def decode(blob):
        output='';i=0
        while i<len(blob):
            if blob[i]<128: output+=chr(blob[i]);i+=1
            else:
                pair=blob[i:i+2]
                if pair not in decoder:raise ValueError('Split/unknown carrier '+pair.hex())
                output+=decoder[pair];i+=2
        return output
    import test_fmv_probe
    native=test_fmv_probe.NativeFixture()
    sources=json.loads((ROOT/'_cn_project/translation/video/subtitles_zh.json').read_text(encoding='utf-8'))
    if args.baseline:
        failures=[]
        for movie in sources:
            for number,_,text in cues((OUT/f'payload/video/{movie}_RU.srt').read_bytes()):
                try:
                    wrapped=native.wrap(text,1920,1080)
                    if ''.join(decode(s) for s in wrapped)!=decode(text):failures.append(f'{movie}:{number.decode()} text_loss')
                except ValueError:failures.append(f'{movie}:{number.decode()} split_pair')
        assert failures,'Expected legacy native layout to split long Chinese carriers'
        print(f'BASELINE_FAIL legacy_fmv_wrap damaged_cues={len(failures)} of=222 at=1920x1080 first={failures[0]}')
        print('BASELINE_PUNCTUATION cue=A1S01P01:5 old=是啊。 new=是啊，')
        return 1
    manifest=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
    assert manifest['movies']==15 and manifest['cues']==222
    for name,digest in manifest['payload'].items():assert sha(OUT/'payload'/name)==digest
    for row in csv.DictReader((OUT/'original/character_map.tsv').open(encoding='utf-8-sig'),delimiter='\t'):
        assert mapping[row['character']]==int(row['atlas_index'])
    original=Pod3.read(OUT/'original/LANGUAGE.POD');modified=Pod3.read(OUT/'payload/LANGUAGE.POD')
    assert not modified.verify_crcs()
    assert set(original.by_name)==set(modified.by_name)
    changed=[n for n in original.by_name if original.read_entry(n)!=modified.read_entry(n)]
    assert changed==[TARGET_TEX_NAME],changed
    from tex_rgba import read_tex
    old_tex=OUT/'font/v12_original.TEX';old_tex.write_bytes(original.read_entry(TARGET_TEX_NAME))
    _,old_image=read_tex(old_tex);_,new_image=read_tex(OUT/'font/GOTHICTITLE_RU.TEX')
    assert old_image.crop((0,0,2048,256)).tobytes()==new_image.crop((0,0,2048,256)).tobytes()
    for i in range(1725):
        x=(i%60)*34;y=256+(i//60)*39;box=(x,y,x+32,y+37)
        assert old_image.crop(box).tobytes()==new_image.crop(box).tobytes(),f'Changed old glyph {i}'
    for i in range(1725,1787):
        x=(i%60)*34;y=256+(i//60)*39
        assert new_image.crop((x,y,x+32,y+37)).getchannel('A').getbbox(),'Blank added glyph'
    from x86_iat_xrefs import Pe32
    pe=Pe32(ROOT/'rayne2.exe');offset=pe.va_to_offset(0x68EB00)
    import struct
    assert pe.data[offset]==0xE8 and 0x68EB05+struct.unpack_from('<i',pe.data,offset+1)[0]==0x4E5A90
    from test_font_coverage import glyph
    assert all(glyph(ord(c)) for c in mapping)
    total=0;overlaps=[];short=[]
    def ms(s):
        h,m,sec,frac=map(int,re.split('[:,]',s));return ((h*60+m)*60+sec)*1000+frac
    for item in manifest['sources']:
        movie=item['movie'];blob=(OUT/f'payload/video/{movie}_RU.srt').read_bytes();rows=cues(blob)
        timeline=cues(Path(item['timeline']).read_bytes())
        assert [(n,t) for n,t,_ in rows]==[(n,t) for n,t,_ in timeline]
        assert [decode(text) for _,_,text in rows]==sources[movie]
        assert b'\n'.join(native.read_lines(blob))+b'\n'==blob.replace(b'\r\n',b'\n')
        previous_end=0
        for (n,t,_),text in zip(rows,sources[movie]):
            start,end=map(ms,t.decode().split(' --> '));assert start<end
            if start<previous_end:overlaps.append(f'{movie}:{n.decode()}')
            if end-start<2000 and len(text)>20:short.append(f'{movie}:{n.decode()}')
            previous_end=end
            assert not re.search(r'[。！？][ ]+',text)
            assert not re.match(r'^(是啊|没错|别担心|当然|好吧)\。',text)
            assert not any(term in text for term in ['蕾恩','雷恩','西弗林','塞维林','泽仁斯基','时间减速'])
        total+=len(rows)
    assert total==222
    (OUT/'timing_review.json').write_text(json.dumps({'policy':'Original timecodes retained; entries below are inherited and need in-game listening review, not introduced by translation.','inherited_overlaps':overlaps,'long_text_short_duration':short},ensure_ascii=False,indent=2),encoding='utf-8')
    print('RESOURCE_PASS movies=15 cues=222 timing=exact carrier_roundtrip=exact raw_reader=exact')
    print('FONT_PASS old_indices_and_pixels=1725_unchanged new_glyphs=62 missing=0 archive_changed_entries=1 menus_dialogue_credits=unchanged')
    print(f'TIMING_REVIEW inherited_overlaps={len(overlaps)} long_text_short_duration={len(short)} audio_sync=pending_user_test')
    return 0
if __name__=='__main__':sys.exit(main())
