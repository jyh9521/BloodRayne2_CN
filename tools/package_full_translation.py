"""Build a release ZIP and execute only standalone/isolated tests. No game launch."""
from pathlib import Path
import subprocess,sys,json,hashlib,zipfile,difflib,os

ROOT=Path(__file__).resolve().parents[2]
PROJECT=ROOT/'_cn_project'
RECORD=PROJECT/'build'/'release_20260923'
RELEASE=PROJECT/'releases'/'v12-20260923'
PYTHON=sys.executable
RELEASE.mkdir(parents=True,exist_ok=True)
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        while b:=f.read(1024*1024): h.update(b)
    return h.hexdigest().upper()

tests=[
 ('BASELINE', ['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(PROJECT/'tools'/'test_dynamic_hook.ps1'),'-Baseline'],1),
 ('MODIFIED', ['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(PROJECT/'tools'/'test_dynamic_hook.ps1')],0),
 ('POD_REBUILD',[PYTHON,'-X','utf8',str(PROJECT/'tools'/'test_pod3_rebuild.py')],0),
 ('FULL_RESOURCE_VALIDATION',[PYTHON,'-X','utf8',str(PROJECT/'tools'/'validate_full_translation.py')],0),
 ('ROLLBACK_AND_DEPLOYMENT',[PYTHON,'-X','utf8',str(PROJECT/'tools'/'test_self_contained_deployment.py')],0),
 ('INSTALLED_V10_ROLLBACK_COPY',[PYTHON,'-X','utf8',str(PROJECT/'tools'/'test_legacy_v9_restore.py')],0),
]
records=[]
for name,cmd,expected in tests:
    p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace')
    r=dict(test=name,command=subprocess.list2cmdline(cmd),stdout=p.stdout,stderr=p.stderr,exit_status=p.returncode,expected_exit=expected)
    records.append(r)
    (RECORD/'tests.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    assert p.returncode==expected,(name,p.stdout,p.stderr)
    print(name+': PASS (exit '+str(p.returncode)+')',flush=True)

before=json.loads((RECORD/'installed_before.json').read_text(encoding='utf-8-sig'))
for row in before: assert sha(Path(row['Path']))==row['Hash'],row['Path']
print('INSTALLED_FILES_UNCHANGED: PASS',flush=True)

manifest=json.loads((PROJECT/'build'/'full_translation'/'manifest.json').read_text(encoding='utf-8'))
assert manifest['build_id']=='full-zh-v12-20260923'
assert manifest['translations']['dialogue_modes']==dict(translated=2595,blank=3)
for relative,digest in manifest['translation_inputs'].items():
    assert sha(PROJECT/'translation'/relative)==digest

differences=[]
for relative in ['proxy/dinput8_cn.cpp','tools/build_full_translation.py','test_package/install_menu_probe.ps1','test_package/README.md','test_package/INSTALL_FULL_TRANSLATION_TEST.cmd','test_package/INSTALL_MENU_TEST.cmd','test_package/RESTORE_PURE.cmd']:
    p=PROJECT/relative; original=RECORD/'original'/p.name
    differences.extend(difflib.unified_diff(original.read_text(encoding='utf-8-sig').splitlines(True),p.read_text(encoding='utf-8-sig').splitlines(True),fromfile=str(original),tofile=str(p)))
(RELEASE/'DIFF_FILE.diff').write_text(''.join(differences),encoding='utf-8')

paths=[PROJECT/'test_package'/n for n in ['INSTALL_FULL_TRANSLATION_TEST.cmd','INSTALL_MENU_TEST.cmd','RESTORE_PURE.cmd','install_menu_probe.ps1','restore_pure.ps1','ROLLBACK.sh','README.md']]
paths += [PROJECT/'build'/'full_translation'/'LANGUAGE.POD',PROJECT/'build'/'full_translation'/'manifest.json',PROJECT/'build'/'full_translation'/'character_map.tsv',PROJECT/'build'/'proxy'/'dinput8.dll',PROJECT/'baseline'/'LANGUAGE.POD']
archive=RELEASE/'BloodRayne2_CN_v12_20260923.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for p in paths:
        z.write(p,p.relative_to(ROOT).as_posix())
    z.writestr('_cn_project/logs/.keep','')
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for p in paths: assert hashlib.sha256(z.read(p.relative_to(ROOT).as_posix())).hexdigest().upper()==sha(p)
    assert not any(n in z.namelist() for n in ['rayne2.exe','W32ART.POD','W32ENSND.POD'])

lines=[
 'BloodRayne 2 Chinese test release v12 / 2026-09-23',
 'MODIFIED_FILE: '+str(PROJECT/'build'/'full_translation'/'LANGUAGE.POD'),
 'PROXY: '+str(PROJECT/'build'/'proxy'/'dinput8.dll'),
 'DIFF_FILE: '+str(RELEASE/'DIFF_FILE.diff'),
 'VERIFICATION: '+str(RELEASE/'VERIFICATION.txt'),
 'ROLLBACK.sh: '+str(PROJECT/'test_package'/'ROLLBACK.sh'),
 'WINDOWS_ROLLBACK: '+str(PROJECT/'test_package'/'RESTORE_PURE.cmd'),
 'ZIP: '+str(archive),
 'Changed field: full translation resources; E9 displacement based on execution_address rather than scratch buffer.',
 'Baseline diagnostic input: copied old proxy source + synthetic x86 font function (no game loaded).',
 'Modified diagnostic input: fixed proxy source + same synthetic x86 function.',
 'Rollback input: temporary game-directory fixtures and isolated copy of installed v10.',
 'Restored behavior: original language bytes, no test DLL, replacement art/sound mods preserved.',
 'Original game files were read and hashed only; no game launch, no in-place install.',
 'LANGUAGE.POD SHA256: '+sha(PROJECT/'build'/'full_translation'/'LANGUAGE.POD'),
 'dinput8.dll SHA256: '+sha(PROJECT/'build'/'proxy'/'dinput8.dll'),
 'ZIP SHA256: '+sha(archive),
 'Previous build LANGUAGE.POD SHA256: '+sha(RECORD/'original'/'LANGUAGE.POD'),
 'Original proxy source SHA256: '+sha(RECORD/'original'/'dinput8_cn.cpp'),
 'Current installed hashes unchanged: '+json.dumps(before,ensure_ascii=False),
 'Tests are resource/standalone/isolated-file tests, not in-game validation.',
 'Payload counts: menu=740 (739 Chinese + 1 blank), moves=94, dialogue=2595 Chinese + 3 clear, unique=1704 Chinese + 2 blank.',
 'English credits byte-exact; English voice memory branch retained; W32ART/W32ENSND files excluded.',
 'User steps on this host: RESTORE_PURE.cmd (v10) -> INSTALL_FULL_TRANSLATION_TEST.cmd (v12) -> user launches game with Russian text container.',
 'No extraction is needed on this host; ZIP is an optional portable copy.',
]
for r in records:
    lines += ['',r['test'],'COMMAND: '+r['command'],'LITERAL STDOUT:',r['stdout'].rstrip(),'LITERAL STDERR:',r['stderr'].rstrip(),'EXIT: '+str(r['exit_status'])]
(RELEASE/'VERIFICATION.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8-sig')
(RELEASE/'sha256.json').write_text(json.dumps({str(p.relative_to(ROOT)):sha(p) for p in paths+[archive]},indent=2),encoding='utf-8')
for p in paths+[archive,RELEASE/'VERIFICATION.txt',RELEASE/'DIFF_FILE.diff']:
    with p.open('rb') as f: assert f.read(1)
print('REOPEN_ALL: PASS',flush=True)
print('RELEASE_READY '+str(archive)+' bytes='+str(archive.stat().st_size),flush=True)
