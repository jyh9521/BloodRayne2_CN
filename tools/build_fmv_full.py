"""Build complete FMV subtitles and extend (never reorder) the v12 atlas."""
from pathlib import Path
import csv, json, re, shutil, struct
from build_fmv_probe import ROOT, cues, sha
from build_full_translation import build_font_texture, TARGET_TEX_NAME, carrier_pair
from pod3 import Pod3, rebuild_entries
from tex_rgba import write_tex

OUT = ROOT / '_cn_project/releases/fmv-full-20260925'
SOURCE = ROOT / '_cn_project/translation/video/subtitles_zh.json'
PROXY = ROOT / '_cn_project/proxy/fmv_full'
OLD_BUILD = ROOT / '_cn_project/build/full_translation'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'original').mkdir(exist_ok=True)
    originals=OUT/'original/live_hashes.json'
    if not originals.exists():
        names=['LANGUAGE.POD','dinput8.dll','rayne2.exe','W32ART.POD','W32ENSND.POD']
        names += [str(p.relative_to(ROOT)) for p in sorted((ROOT/'video').iterdir()) if p.is_file()]
        before={n:sha(ROOT/n) for n in names}
        originals.write_text(json.dumps(before,indent=2),encoding='utf-8')
        for name in ['LANGUAGE.POD','dinput8.dll']:
            shutil.copy2(ROOT/name,OUT/'original'/name)
        shutil.copy2(ROOT/'_cn_project/proxy/dinput8_cn.cpp',OUT/'original/dinput8_cn.cpp')
        shutil.copy2(OLD_BUILD/'character_map.tsv',OUT/'original/character_map.tsv')
        for p in (ROOT/'video').glob('*_RU.srt'):
            shutil.copy2(p,OUT/'original'/p.name)
    before=json.loads(originals.read_text(encoding='utf-8'))
    assert before['LANGUAGE.POD']=='5CF475C4E80F3245ABA654870DDEF5F2BABF6A4805537C521B01CAC44B9EE577'
    assert before['dinput8.dll']=='91326E4B91662C0ABE4DD8628CA7CBFBC19637154A717724DBEF353CFC51FC43'
    translations=json.loads(SOURCE.read_text(encoding='utf-8'))
    assert set(translations)=={p.stem[:-3] for p in (ROOT/'video').glob('*_FR.srt')}
    mapping={r['character']:int(r['atlas_index']) for r in csv.DictReader((OUT/'original/character_map.tsv').open(encoding='utf-8-sig'),delimiter='\t')}
    old_count=len(mapping)
    extra=sorted({c for texts in translations.values() for s in texts for c in s if ord(c)>=128}-set(mapping),key=ord)
    for c in extra: mapping[c]=len(mapping)
    assert len(mapping)<=2914
    sources=[]
    glossary=json.loads(json.dumps({'Rayne':'莱恩','Severin':'塞弗林','Brimstone':'硫磺会','Kagan':'卡根','Zerenski':'泽伦斯基','Xerx':'泽克斯','Ephemera':'埃菲梅拉','Ferril':'费里尔','Slezz':'斯莱兹','Tremayne':'特雷梅恩','Kestrel':'红隼','Carpathian Dragons':'喀尔巴阡龙枪','Vesper Shard':'暮星碎片','Shroud':'暗幕','Unraveler':'拆解者','Sun Cannon':'太阳炮','Dariel':'达里尔','Brewster':'布鲁斯特','DeHesto':'德赫斯托','Megostophile':'梅戈斯托菲尔'},ensure_ascii=False))
    details=[]
    for movie,texts in translations.items():
        fr=ROOT/f'video/{movie}_FR.srt'
        timeline=fr
        if movie=='A1S01P01':
            timeline=ROOT/'_cn_project/releases/fmv-probe-20260923/original/A1S01P01_RU.srt'
        source_cues=cues(timeline.read_bytes())
        assert len(source_cues)==len(texts)
        plain, encoded=[],[]
        for i,((number,stamp,_),text) in enumerate(zip(source_cues,texts),1):
            assert text.strip()==text and not re.search(r'[\r\n\t]',text)
            assert not re.search(r'[。！？][ ]+',text), 'Remove Western sentence spacing'
            # Western full stops in short Chinese interjections are intentional
            # review failures; questions and complete statements remain separate.
            assert not re.search(r'^(是啊|没错|当然|别担心|好吧|嗯)\。',text)
            body=b''.join(bytes([ord(c)]) if ord(c)<128 else bytes(carrier_pair(mapping[c])) for c in text)
            assert len(body)<1022 and len(set(c for c in text if ord(c)>=128))<=94
            head=number+b'\r\n'+stamp+b'\r\n'
            plain.append(head+text.encode('utf-8')+b'\r\n\r\n')
            encoded.append(head+body+b'\r\n\r\n')
            details.append({'movie':movie,'cue':i,'timestamp':stamp.decode(),'text':text,'bytes':len(body)})
        for sub,blob in [('source',b''.join(plain)),('payload/video',b''.join(encoded))]:
            p=OUT/sub/(movie+('_ZH.utf8.srt' if sub=='source' else '_RU.srt'))
            p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(blob)
        sources.append({'movie':movie,'cues':len(texts),'translation_reference':str(fr),'reference_sha256':sha(fr),'timeline':str(timeline),'timeline_sha256':sha(timeline)})
    (OUT/'source/subtitles_zh.json').write_bytes(SOURCE.read_bytes())
    (OUT/'source/glossary.json').write_text(json.dumps(glossary,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'character_map.json').write_text(json.dumps(mapping,ensure_ascii=False,indent=2),encoding='utf-8')
    header,image=build_font_texture(mapping)
    tex=OUT/'font/GOTHICTITLE_RU.TEX';tex.parent.mkdir(exist_ok=True)
    write_tex(tex,header,image)
    pod=Pod3.read(OUT/'original/LANGUAGE.POD')
    built=OUT/'payload/LANGUAGE.POD'
    built.write_bytes(rebuild_entries(pod.data,{TARGET_TEX_NAME:tex.read_bytes()},{}))
    assert not Pod3.read(built).verify_crcs()
    # Generate traits in the carrier space; no runtime Unicode/locale conversion.
    PROXY.mkdir(parents=True,exist_ok=True)
    traits=[]
    for char,kind in [(c,1) for c in '，。、！？；：）》】」』”’']+[(c,2) for c in '（《【「『“‘']:
        if char in mapping:
            lead,tail=carrier_pair(mapping[char]);traits.append(f'    case 0x{lead:02X}{tail:02X}: return {kind};')
    (PROXY/'fmv_punctuation.h').write_text('inline int FmvPunctuation(unsigned short code) {\n    switch(code) {\n'+'\n'.join(traits)+'\n    default: return 0;\n    }\n}\n',encoding='ascii')
    # Preserve doubled ellipsis/em dash groups during line wrapping.
    for c,n in [('…','kFmvEllipsis'),('—','kFmvDash')]:
        pair=carrier_pair(mapping[c]) if c in mapping else (0,0)
        with (PROXY/'fmv_punctuation.h').open('a',encoding='ascii') as f: f.write(f'constexpr unsigned short {n}=0x{pair[0]:02X}{pair[1]:02X};\n')
    manifest={'build_id':'fmv-full-v13-20260925','movies':len(translations),'cues':len(details),'glyphs_previous':old_count,'glyphs_total':len(mapping),'glyphs_added':extra,'old_indices_preserved':True,'sources':sources,'required_before':{n:before[n] for n in ['LANGUAGE.POD','dinput8.dll','rayne2.exe']},'payload':{'LANGUAGE.POD':sha(built),**{f'video/{m}_RU.srt':sha(OUT/f'payload/video/{m}_RU.srt') for m in translations}},'untranslated_bik':['demo','logos','PROLOG','ziggurat'],'punctuation':'Chinese semantic segmentation; no Western sentence spacing; explicit comma after interjections where part of same sentence','timeline_policy':'Preserve reference timestamps. Opening retains user-tested timings; other 14 use bundled FR. Existing overlaps and short cues are retained pending listening tests.'}
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'cue_details.json').write_text(json.dumps(details,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'BUILD_PASS movies={len(translations)} cues={len(details)} glyphs={old_count}+{len(extra)}={len(mapping)} max_cue_bytes={max(r["bytes"] for r in details)}')
    print('NEW_GLYPHS '+''.join(extra))

if __name__=='__main__':main()
