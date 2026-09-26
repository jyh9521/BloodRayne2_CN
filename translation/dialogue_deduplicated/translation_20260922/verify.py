from pathlib import Path
import sys, subprocess, json, shutil, re
from collections import Counter
import finish_translation as ft

HERE=Path(__file__).resolve().parent
MODE=sys.argv[1]
if MODE=='baseline':
    fields,rows=ft.read(ft.ORIGINAL)
    assert len(rows)==1706 and ft.digest(ft.ORIGINAL)=='148CC725BEB24FFA5F3081FB744598822C98DF19247351AB4B8BFCB5FD0C8B0E'
    assert Counter(r['status'] for r in rows)==Counter(translated=114,needs_review=125,pending=1465,blank=2)
    print('BASELINE_OK rows=1706 translated=114 needs_review=125 pending=1465 blank=2')
elif MODE=='modified':
    # Original importer's actual selection and carrier encoder: read only, no game/POD writes.
    sys.path.insert(0,str(HERE.parents[2]/'tools'))
    import build_full_translation as b
    assert ft.audit(ft.TARGET)==0
    occurrences,sources,unique=b.load_dialogue_plan()
    selections=[b.choose_dialogue_text(o,sources,unique) for o in occurrences]
    assert Counter(mode for text,mode in selections)==Counter(translated=2595,blank=3)
    menu=b.load_menu_rows(); moves=b.load_move_rows()
    texts=[r['translation_zh'] for r in menu+moves]+[t for t,m in selections]
    mapping=b.ordered_character_map(texts)
    maximum=max(len({c for c in t if ord(c)>=128}) for t in texts)
    assert maximum<=b.TAIL_COUNT, maximum
    for text in texts:
        encoded=b.encode_text(text,mapping)
        out=[]; i=0; inverse={v:k for k,v in mapping.items()}
        while i<len(encoded):
            x=encoded[i]; i+=1
            if x<128: out.append(chr(x))
            else:
                y=encoded[i];i+=1
                out.append(inverse[(x-b.LEAD_MIN)*b.TAIL_COUNT+y-b.TAIL_MIN])
        assert ''.join(out)==text
    _,rows=ft.read(ft.TARGET); _,orig=ft.read(ft.ORIGINAL)
    resolved=[dict(unit_id=r['unit_id'],source_en=r['source_en'],translation_zh=r['translation_zh'],original_variants=o['notes']) for r,o in zip(rows,orig) if o['status']=='needs_review']
    assert len(resolved)==125
    ft.write(HERE/'resolved_conflicts.tsv',list(resolved[0]),resolved)
    residual=[]
    for i,r in enumerate(rows):
        t=re.sub(r'@@[^@]+@@','',r['translation_zh'])
        if re.search(r'[A-Za-z]{3,}',t): residual.append(dict(index=i,source=r['source_en'],translation=r['translation_zh']))
    (HERE/'retained_source_markers.json').write_text(json.dumps(residual,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'MODIFIED_OK translated=1704 conflicts_resolved=125 pending=0 occurrences=2595 clear=3 terms={len(ft.TERMS)} tokens=PASS carrier_roundtrip=PASS glyphs={len(mapping)}/{b.CARRIER_CAPACITY} max_draw={maximum}/{b.TAIL_COUNT}')
elif MODE=='rollback':
    before=ft.digest(ft.TARGET)
    sandbox=HERE/'rollback_test.tsv'
    shutil.copy2(ft.TARGET,sandbox)
    bash=Path('C:/Program Files/Git/bin/bash.exe')
    p=subprocess.run([str(bash),str(HERE/'ROLLBACK.sh'),str(sandbox)],capture_output=True,text=True,encoding='utf-8')
    print(p.stdout.strip()); assert p.returncode==0,p.stderr
    assert sandbox.read_bytes()==ft.ORIGINAL.read_bytes()
    assert ft.digest(ft.TARGET)==before
    print('ROLLBACK_TEST_OK restored=byte-identical modified_file=unchanged')
else: raise ValueError(MODE)
