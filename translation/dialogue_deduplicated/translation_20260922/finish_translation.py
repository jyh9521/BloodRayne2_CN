from pathlib import Path
import csv, re, json, hashlib, sys, difflib, shutil
from collections import Counter, defaultdict

HERE = Path(__file__).resolve().parent
TARGET = HERE.parent / 'dialogue_unique.tsv'
ORIGINAL = HERE / 'dialogue_unique.original.tsv'
PYTHON = sys.executable
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest().upper()
def read(p):
    with p.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f, delimiter='\t')
        return reader.fieldnames, list(reader)
def write(p, fields, rows):
    with p.open('w', encoding='utf-8-sig', newline='') as f:
        w=csv.DictWriter(f, fields, delimiter='\t', lineterminator='\r\n')
        w.writeheader(); w.writerows(rows)

TERMS = [
 ('Rayne','莱恩',r'\bRayne\b'),('BloodRayne','吸血莱恩',r'\bBloodRayne\b'),
 ('Severin / Severen','塞弗林',r'\bSever[ie]n\b'),('Kagan','卡根',r'\bKagan\b'),
 ('Zerenski / Zerenzki','泽伦斯基',r'\bZeren[sz]ki\b'),('Ephemera','埃菲梅拉',r'\bEphemera\b'),
 ('Ferril','费里尔',r'\bFerril\b'),('Slezz','斯莱兹',r'\bSlezz\b'),('Xerx','泽克斯',r'\bXerx\b'),
 ('Llewelyn','卢埃林',r'\bLlewelyn\b'),('Delinda','德琳达',r'\bDelinda\b'),
 ('Gardath','加达斯',r'\bGardath\b'),('Loestrum','洛斯特伦',r'\bLoestrum\b'),
 ('Victor','维克托',r'\bVictor\b'),('Tremayne','特雷梅恩',r'\bTremayne\b'),
 ('Mynce','明斯',r'\bMynce\b'),('Esgoth','埃斯戈斯',r'\bEsgoth\b'),
 ('Kimsui','基姆苏伊',r'\bKimsui\b'),('Mora','莫拉',r'\bMora\b'),('Lockdown','洛克当',r'\bLockdown\b'),
 ('Brimstone / Brimstone Society','硫磺会',r'\bBrimstone\b'),
 ('Kestrel / Kestral','红隼',r'\bKestr[ae]ls?\b'),('Shakab','沙卡布',r'\bShakab\b'),
 ('Trauger / Traujer Elite','特劳格精锐',r'\bTrau[gj]er Elite[s]?\b'),
 ('Unraveler / Unraveller','拆解者',r'\bUnravell?er\b'),
 ('Shadow Legion','暗影军团',r'\bShadow Legion\b'),('Roach Golem','蟑螂魔像',r'\bRoach Golems?\b'),
 ('Dhampir','半吸血鬼',r'\bDhampir\b'),('Brute','蛮兽',r'\bBrutes?\b'),
 ('Foreman','工头',r'\bForem[ae]n\b'),('Mancow','人牛',r'\bMancow\b'),
 ('BioMech','生物机甲',r'\bBioMechs?\b'),('Bio Armor / Bioarmor','生物装甲',r'\bBio ?Armor\b'),
 ('Shroud','暗幕',r'\bShroud\b'),('Wetworks','血液工厂',r'\bWetworks\b'),
 ('Meatpacking District','肉类加工区',r'\bMeatpacking District\b'),
 ("Ray Ray's Meats","雷雷肉联厂",r"\bRay Ray's(?: Meats)?\b"),
 ('Union Station','联合车站',r'\bUnion Station\b'),('Club Strages','斯特拉吉斯俱乐部',r'\bClub Strages\b'),
 ('Twisted Park','扭曲公园',r'\bTwisted Park\b'),('Neon City','霓虹城',r'\bNeon City\b'),
 ("O'Leary's Cow","奥利里的牛酒吧",r"\bO'Leary's Cow\b"),
 ('Vesper Shard','暮星碎片',r'\bVesper Shard\b'),('Carpathian Dragons','喀尔巴阡龙枪',r'\bCarpathian(?: Dragons)?\b'),
 ('Dark Gift','黑暗赐福',r'\bDark Gift\b'),('Bloodfield','血界',r'\bBloodfield\b'),
 ('Aura Vision','灵视',r'\bAura Vision\b'),('Dilated Perception','时间感知',r'\bDilated Perception\b'),
 ('Blood Rage','血怒',r'\bBlood Rage\b'),('Blood Fury','血之狂暴',r'\bBlood Fury\b'),
 ('Blood Storm','血之风暴',r'\bBlood Storm\b'),('Ghost Feed','幽灵吸血',r'\bGhost Feed\b'),
 ('Enthrall','魅惑',r'\bEnthrall\b'),('Super Speed','超级速度',r'\bSuper Speed\b'),
 ('Freeze Time','时间冻结',r'\bFreeze Time\b'),('Blood Stream','血流',r'\bBlood Stream\b'),
 ('Blood Spray','血雾',r'\bBlood Spray\b'),('Blood Bomb','血爆',r'\bBlood Bomb\b'),
 ('Blood Flame','血焰',r'\bBlood Flame\b'),('Blood Hammer','血锤',r'\bBlood Hammer\b'),
 ('Twisted Wind','扭风',r'\bTwisted Wind\b'),('Silver Circlet','银环',r'\bSilver Circlet\b'),
 ('Quiet Thunder','静雷',r'\bQuiet Thunder\b'),('Shiva Aspect','湿婆化身',r'\bShiva Aspect\b'),
 ('Curtain Twice Torn','帷幕再裂',r'\bCurtain Twice Torn\b'),('Punishment Blade','惩罚之刃',r'\bPunishment Blade\b'),
 ('Sun Cannon / Sungun / Solar Cannon','太阳炮',r'\b(?:sun ?cannon|sungun|solar cannon)\b'),
 ('Shepherd','牧羊人',r'\bShepherds?\b'),('Carnage points','杀戮点数',r'\bCarnage points\b'),
 ('West Indies','西印度群岛',r'\bWest Indies\b'),('Babylonian','巴比伦',r'\bBabylonian\b'),
 ('Sumatran','苏门答腊',r'\bSumatran\b'),('Dragons / Dragon pistols','龙枪',r'\bDragons?\b')
]
SPEAKER_EN=re.compile(r'^(?:Rayne|Severin|Severen|Zerenzki|Zerenski|Dhampir|Minion(?: [12])?|Kestrel|Ephemera|Ferril|Xerx|Brute|Punk(?: [12])?|Civilian|Thug|Mynce):\s*', re.I)
SPEAKER_ZH=re.compile(r'^(?:莱恩|蕾恩|塞弗林|泽伦斯基|半吸血鬼|仆从|喽啰[12]?|红隼|埃菲梅拉|费里尔|泽克斯|蛮兽|混混[12]?|平民|暴徒|明斯)：\s*')

def build():
    fields, rows=read(ORIGINAL)
    overrides={}
    for p in [HERE/'translations.txt']+sorted(HERE.glob('batch*.txt')):
        for line in p.read_text(encoding='utf-8').splitlines():
            n,t=line.split('|',1); n=int(n)
            assert n not in overrides, n
            overrides[n]=t
    for i,r in enumerate(rows):
        if r['status']=='blank':
            r['translation_zh']=''; continue
        old=r['translation_zh']
        t=overrides.get(i,old)
        assert t, (i,r['source_en'])
        if i not in overrides and not SPEAKER_EN.match(r['source_en']): t=SPEAKER_ZH.sub('',t)
        for a,b in [('蕾恩','莱恩'),('灵光视觉','灵视'),('感知扩张','时间感知'),('龙式手枪','龙枪')]: t=t.replace(a,b)
        r['translation_zh']=t
        r['status']='translated'
        if r['notes'].startswith('needs review:'):
            r['notes']='Resolved 2026-09-22: context-reviewed unified translation; historical variants retained for reference. '+r['notes'].replace('needs review:','Original conflict:',1).replace('the first occurrence is retained','previously the first occurrence was retained',1)
    # One exact English sentence gets one final translation, even if its RU variants differ.
    groups=defaultdict(list)
    for i,r in enumerate(rows):
        if r['source_en'] and r['status']!='blank': groups[r['source_en']].append(i)
    for ids in groups.values():
        chosen=next((i for i in ids if i in overrides),ids[0])
        for i in ids: rows[i]['translation_zh']=rows[chosen]['translation_zh']
    write(TARGET,fields,rows)
    (HERE/'DIFF_FILE.diff').write_text(''.join(difflib.unified_diff(ORIGINAL.read_text(encoding='utf-8-sig').splitlines(True),TARGET.read_text(encoding='utf-8-sig').splitlines(True),fromfile=str(ORIGINAL),tofile=str(TARGET))),encoding='utf-8')
    write(HERE.parent/'glossary_zh.tsv',['source_term','translation_zh','match_pattern','policy'],[dict(source_term=a,translation_zh=b,match_pattern=c,policy='项目统一译名；优先沿用菜单与已有译文，新增词为本项目译法，非官方译名声明') for a,b,c in TERMS])
    print('BUILD_OK rows='+str(len(rows)))

def audit(path):
    fields,rows=read(path); of,original=read(ORIGINAL)
    assert fields==of and len(rows)==len(original)==1706
    immutable=[x for x in fields if x not in ['translation_zh','status','notes']]
    errors=[]; term_errors=[]
    for i,(r,o) in enumerate(zip(rows,original)):
        assert all(r[k]==o[k] for k in immutable), ('immutable',i)
        t=r['translation_zh']; s=r['source_en'] or r['source_ru']
        if o['status']=='blank':
            if t or r['status']!='blank': errors.append(['blank',i])
            continue
        if r['status']!='translated' or not t: errors.append(['unfinished',i])
        for pat in [r'@@[^@]+@@',r'%(?:\d+\$)?[-+#0 ]*(?:\d+|\*)?(?:\.\d+|\.\*)?[hlLzjtI]*[diuoxXfFeEgGaAcspn%]']:
            if Counter(re.findall(pat,s))!=Counter(re.findall(pat,t)): errors.append(['tokens',i])
        for a,b,p in TERMS:
            if re.search(p,s,re.I) and b not in t: term_errors.append([i,a,b,t])
    mapping=read(HERE.parent/'dialogue_occurrences.tsv')[1]
    ids=Counter(r['unit_id'] for r in mapping)
    assert len(mapping)==2598 and set(ids)=={r['unit_id'] for r in rows}
    assert all(ids[r['unit_id']]==int(r['occurrence_count']) for r in rows)
    counts=dict(Counter(r['status'] for r in rows))
    result={'rows':len(rows),'status':counts,'occurrences':len(mapping),'translated_occurrences':sum(int(r['occurrence_count']) for r in rows if r['status']=='translated'),'blank_occurrences':sum(int(r['occurrence_count']) for r in rows if r['status']=='blank'),'errors':errors,'term_errors':term_errors,'sha256':digest(path)}
    print(json.dumps(result,ensure_ascii=False))
    return 1 if errors or term_errors else 0

if __name__=='__main__':
    if sys.argv[1]=='build': build()
    elif sys.argv[1]=='audit': sys.exit(audit(Path(sys.argv[2])))
