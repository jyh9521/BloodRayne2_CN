import difflib,json,shutil,subprocess,sys,zipfile
from pathlib import Path
from build_fmv_full import ROOT,OUT
from build_fmv_probe import sha

BUILD=ROOT/'_cn_project/build/fmv_full_20260925'
FIXTURE=BUILD/'deployment_fixture'
PS='C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe'
BASH='C:/Program Files/Git/bin/bash.exe'
RECORDS=[]

def run(label,command,expected=0,input_description=''):
    result=subprocess.run([str(x) for x in command],capture_output=True,text=True,encoding='utf-8',errors='replace',cwd=ROOT)
    RECORDS.append({'label':label,'command':subprocess.list2cmdline([str(x) for x in command]),'input':input_description,'stdout':result.stdout,'stderr':result.stderr,'exit':result.returncode,'expected':expected})
    assert result.returncode==expected,RECORDS[-1]
    print(f'{label}: PASS expected_exit={expected} actual_exit={result.returncode}',flush=True)

def powershell(script,package=OUT):return [PS,'-NoProfile','-ExecutionPolicy','Bypass','-File',package/script,'-GameRoot',FIXTURE]
def snap(names):return {n:sha(FIXTURE/n) if (FIXTURE/n).exists() else None for n in names}

def main():
    m=json.loads((OUT/'manifest.json').read_text(encoding='utf-8-sig'))
    before=json.loads((OUT/'original/live_hashes.json').read_text(encoding='utf-8'))
    assert {n:sha(ROOT/n) for n in before}==before,'User live files changed during build'
    run('BASELINE',[sys.executable,'-X','utf8',ROOT/'_cn_project/tools/validate_fmv_full.py','--baseline'],1,'222 translated cues through the legacy 64-byte native video wrapper at 1920x1080')
    run('MODIFIED',[BUILD/'test_fmv_full.exe'],input_description='Compiled production FMV wrapper; 222 cues, 7 resolutions; real dynamic glyph preparation; isolated synthetic call patch')
    run('RESOURCE_VALIDATION',[sys.executable,'-X','utf8',ROOT/'_cn_project/tools/validate_fmv_full.py'],input_description='Rebuilt LANGUAGE archive, old glyph pixels and indices, 15 SRT timecodes, new font cmap/glyph coverage')
    run('EXISTING_HOOK_REGRESSION',[BUILD/'test_dynamic.exe'],input_description='Isolated executable trampoline and thiscall regression using the new proxy source')
    FIXTURE.mkdir(parents=True,exist_ok=True);(FIXTURE/'video').mkdir(exist_ok=True)
    assert not (FIXTURE/'_cn_project/test_backup/fmv_full_20260925/state.json').exists()
    for n in m['required_before']:shutil.copy2(ROOT/n,FIXTURE/n)
    for n in m['payload']:
        if n.startswith('video/') and (ROOT/n).exists():shutil.copy2(ROOT/n,FIXTURE/n)
    (FIXTURE/'video/A1S01P02_RU.srt').write_bytes(b'EXISTING USER SUBTITLE')
    (FIXTURE/'W32ART.POD').write_bytes(b'ART MOD BEFORE')
    (FIXTURE/'W32ENSND.POD').write_bytes(b'SOUND MOD BEFORE')
    (FIXTURE/'video/A1S01P01.bik').write_bytes(b'BIK VIDEO MUST STAY UNCHANGED')
    names=list(m['payload'])+['rayne2.exe','W32ART.POD','W32ENSND.POD','video/A1S01P01.bik']
    initial=snap(names)
    run('INSTALL_ISOLATED',powershell('install.ps1'),input_description='Isolated copy of v12 + installed opening probe, one other pre-existing user SRT, mod markers, other SRT files absent')
    for n,digest in m['payload'].items():assert sha(FIXTURE/n)==digest
    for n in names:
        if n not in m['payload']:assert snap([n])[n]==initial[n]
    (FIXTURE/'W32ART.POD').write_bytes(b'ART MOD INSTALLED AFTER FMV')
    (FIXTURE/'W32ENSND.POD').write_bytes(b'SOUND MOD INSTALLED AFTER FMV')
    (FIXTURE/'video/A1S01P02_RU.srt').write_bytes(b'LATER USER EDIT')
    postedit=snap(names)
    run('ROLLBACK_EDIT_GUARD',powershell('rollback.ps1'),1,'Later user edit: reject before restoring any file')
    assert snap(names)==postedit
    shutil.copy2(OUT/'payload/video/A1S01P02_RU.srt',FIXTURE/'video/A1S01P02_RU.srt')
    run('ROLLBACK',[BASH,OUT/'ROLLBACK.sh','-GameRoot',FIXTURE],input_description='Isolated installed copy: restore original hashes and originally absent files; preserve newer mods')
    for n in m['payload']:assert snap([n])[n]==initial[n]
    assert (FIXTURE/'W32ART.POD').read_bytes()==b'ART MOD INSTALLED AFTER FMV'
    assert (FIXTURE/'W32ENSND.POD').read_bytes()==b'SOUND MOD INSTALLED AFTER FMV'
    assert sha(FIXTURE/'video/A1S01P01.bik')==initial['video/A1S01P01.bik']
    # Hash mismatch must reject the package before a single deployment write.
    tampered=BUILD/'tampered_package';tampered.mkdir(exist_ok=True)
    for n in ['install.ps1','manifest.json']:shutil.copy2(OUT/n,tampered/n)
    for n in m['payload']:
        dest=tampered/'payload'/n;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(OUT/'payload'/n,dest)
    (tampered/'payload/video/A4S03P04_RU.srt').write_bytes(b'TAMPERED PAYLOAD')
    clean=snap(names)
    run('PACKAGE_HASH_GUARD',powershell('install.ps1',tampered),1,'Tampered final video SRT: all preflight checks happen before writes')
    assert snap(names)==clean
    (FIXTURE/'dinput8.dll').write_bytes(b'OTHER MOD PROXY')
    proxy_modified=snap(names)
    run('DLL_CONFLICT_GUARD',powershell('install.ps1'),1,'Different installed DLL must remain untouched')
    assert snap(names)==proxy_modified
    shutil.copy2(ROOT/'dinput8.dll',FIXTURE/'dinput8.dll')
    assert {n:sha(ROOT/n) for n in before}==before
    print('LIVE_GAME_VIDEO_MOD_FILES_UNCHANGED: PASS',flush=True)
    diff=[]
    original=(OUT/'original/dinput8_cn.cpp').read_text(encoding='utf-8').splitlines(True)
    revised=(ROOT/'_cn_project/proxy/fmv_full/dinput8_cn.cpp').read_text(encoding='utf-8').splitlines(True)
    diff.extend(difflib.unified_diff(original,revised,fromfile='v12/dinput8_cn.cpp',tofile='v13/dinput8_cn.cpp'))
    for name in ['fmv_layout.h','fmv_punctuation.h']:
        lines=(ROOT/'_cn_project/proxy/fmv_full'/name).read_text(encoding='utf-8').splitlines(True)
        diff.extend(difflib.unified_diff([],lines,fromfile='/dev/null',tofile=name))
    for path in sorted((OUT/'source').glob('*_ZH.utf8.srt')):
        old=ROOT/'_cn_project/releases/fmv-probe-20260923/source'/path.name
        diff.extend(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True) if old.exists() else [],path.read_text(encoding='utf-8').splitlines(True),fromfile=str(old) if old.exists() else '/dev/null',tofile=str(path.relative_to(OUT))))
    (OUT/'DIFF_FILE.diff').write_text(''.join(diff),encoding='utf-8')
    (OUT/'tests.json').write_text(json.dumps(RECORDS,ensure_ascii=False,indent=2),encoding='utf-8')
    fields={'MODIFIED_FILE':OUT/'payload/dinput8.dll','MODIFIED_RESOURCE':OUT/'payload/LANGUAGE.POD','DIFF_FILE':OUT/'DIFF_FILE.diff','VERIFICATION':OUT/'VERIFICATION.txt','ROLLBACK':OUT/'ROLLBACK.sh'}
    lines=['FMV full Chinese 2026-09-25',
        'Changed call: rayne2 RVA 0x28EB00, native wrap target RVA 0xE5A90 -> FmvChineseWrap (in memory only).',
        'Changed fields: 222 cue text bodies; Chinese semantic punctuation; 62 appended atlas glyphs.',
        'LANGUAGE.POD only changed entry: ART\\GOTHICTITLE_RU.TEX. Other 387 entries unchanged.',
        'Live game not launched or installed. User confirmed prior opening probe only.',
        '15 external-subtitle movies covered; 4 other BIK files without SRT not translated.',
        'Timecodes preserved from reference; 78 inherited overlaps and 3 unusually short long-text cues require audio review.',
        'Rollback restored v12 runtime and prior SRT contents/absence on isolated copy; later mod markers retained.',
        'MODIFIED_FILE and all payloads remain changed.']
    lines.extend(f'{k}: {v}' for k,v in fields.items())
    lines+=['Original hashes:',json.dumps({n:before[n] for n in m['required_before']},indent=2),'Payload hashes:',json.dumps(m['payload'],indent=2)]
    for r in RECORDS:lines+=['',r['label'],'COMMAND: '+r['command'],'INPUT: '+r['input'],'LITERAL STDOUT:',r['stdout'],'LITERAL STDERR:',r['stderr'],'EXIT: '+str(r['exit'])]
    lines+=['','LIVE_GAME_VIDEO_MOD_FILES_UNCHANGED: PASS',json.dumps(before,indent=2)]
    (OUT/'VERIFICATION.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    # Ship runtime payloads and readable documentation, never compiler .lib/.exp
    # outputs or the user's backed-up game archives.
    files=[OUT/'payload'/n for n in m['payload']]
    files+=list((OUT/'source').glob('*'))
    files+=[OUT/n for n in ['INSTALL.cmd','install.ps1','ROLLBACK.cmd','rollback.ps1','ROLLBACK.sh','README.md','manifest.json','character_map.json','timing_review.json','DIFF_FILE.diff','VERIFICATION.txt','tests.json']]
    archive=OUT/'BloodRayne2_FMV_Chinese_Full_v13.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in files:z.write(p,str(p.relative_to(ROOT)))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for p in files:assert z.read(str(p.relative_to(ROOT)).replace('\\','/'))==p.read_bytes()
    (OUT/'sha256.json').write_text(json.dumps({str(p.relative_to(OUT)):sha(p) for p in files+[archive]},indent=2),encoding='utf-8')
    for p in files+[archive,OUT/'sha256.json']:assert p.read_bytes()
    print(f'PACKAGE_REOPEN_PASS files={len(files)} zip_bytes={archive.stat().st_size}',flush=True)
    print('READY '+str(archive),flush=True)

if __name__=='__main__':main()
