"""Package and test the FMV probe in a separate fixture, never the live game."""
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from build_fmv_probe import ROOT, OUT, sha

FIXTURE = ROOT / '_cn_project/build/fmv_probe_20260923/fixture'
POWERSHELL = 'C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe'
BASH = 'C:/Program Files/Git/bin/bash.exe'
RECORDS = []

def run(label, command, expected=0, input_description=''):
    result = subprocess.run([str(x) for x in command], capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=ROOT)
    RECORDS.append(dict(label=label, command=subprocess.list2cmdline([str(x) for x in command]), input=input_description, stdout=result.stdout, stderr=result.stderr, exit=result.returncode, expected_exit=expected))
    assert result.returncode == expected, RECORDS[-1]
    print(f'{label}: expected_exit={expected} actual_exit={result.returncode} PASS', flush=True)
    return result

def ps(script):
    return [POWERSHELL, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', OUT/script, '-GameRoot', FIXTURE]

def main():
    m = json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
    before = {n:sha(ROOT/n) for n in m['installed_before']}
    assert before == m['installed_before'], 'Live files changed since probe snapshot'
    run('BASELINE', [sys.executable,'-X','utf8',ROOT/'_cn_project/tools/test_fmv_probe.py','--baseline'], 1, 'original/A1S01P01_RU.srt; first cue contains bytes not mapped by v12')
    run('MODIFIED', [sys.executable,'-X','utf8',ROOT/'_cn_project/tools/test_fmv_probe.py'], 0, 'payload/video/A1S01P01_RU.srt; isolated raw-line and wrap emulation; no game process')
    FIXTURE.mkdir(parents=True, exist_ok=True)
    (FIXTURE/'video').mkdir(exist_ok=True)
    assert not (FIXTURE/'_cn_project/test_backup/fmv_probe_20260923/state.json').exists(), 'Unfinished fixture rollback; inspect before rerun'
    for name in m['required_files']:
        shutil.copy2(ROOT/name, FIXTURE/name)
    # The installation does not read or write these two archives; markers
    # explicitly verify preservation even when modded after installation.
    (FIXTURE/'W32ART.POD').write_bytes(b'ART MOD BEFORE INSTALL')
    (FIXTURE/'W32ENSND.POD').write_bytes(b'ENGLISH SOUND MOD BEFORE INSTALL')
    target = FIXTURE/'video/A1S01P01_RU.srt'
    shutil.copy2(OUT/'original/A1S01P01_RU.srt',target)
    run('INSTALL_ISOLATED_COPY',ps('install.ps1'),input_description='Fixture with v12 required files and exact copy of user original SRT')
    assert sha(target) == m['payload_sha256']
    for name,digest in m['required_files'].items(): assert sha(FIXTURE/name)==digest
    assert (FIXTURE/'W32ART.POD').read_bytes()==b'ART MOD BEFORE INSTALL'
    assert (FIXTURE/'W32ENSND.POD').read_bytes()==b'ENGLISH SOUND MOD BEFORE INSTALL'
    (FIXTURE/'W32ART.POD').write_bytes(b'ART MOD AFTER INSTALL')
    (FIXTURE/'W32ENSND.POD').write_bytes(b'ENGLISH SOUND MOD AFTER INSTALL')
    run('ROLLBACK', [BASH,str(OUT/'ROLLBACK.sh'),'-GameRoot',str(FIXTURE)], input_description='Isolated installed copy; existing user SRT must be restored byte-for-byte')
    assert sha(target)==m['original_sha256']
    assert (FIXTURE/'W32ART.POD').read_bytes()==b'ART MOD AFTER INSTALL'
    assert (FIXTURE/'W32ENSND.POD').read_bytes()==b'ENGLISH SOUND MOD AFTER INSTALL'
    # Test the no-original case and a later user edit: rollback must not erase it.
    target.unlink()
    run('INSTALL_ABSENT_SUBTITLE',ps('install.ps1'))
    target.write_bytes(b'USER EDIT AFTER INSTALL')
    run('ROLLBACK_EDIT_GUARD',ps('rollback.ps1'),1)
    assert target.read_bytes()==b'USER EDIT AFTER INSTALL'
    shutil.copy2(OUT/'payload/video/A1S01P01_RU.srt',target)
    run('ROLLBACK_ABSENT_SUBTITLE',ps('rollback.ps1'))
    assert not target.exists()
    (FIXTURE/'dinput8.dll').write_bytes(b'DIFFERENT MOD DLL')
    run('INSTALL_VERSION_GUARD',ps('install.ps1'),1)
    assert not target.exists()
    shutil.copy2(ROOT/'dinput8.dll',FIXTURE/'dinput8.dll')
    shutil.copy2(OUT/'original/A1S01P01_RU.srt',target)
    assert {n:sha(ROOT/n) for n in before}==before
    print('LIVE_FILES_UNCHANGED: PASS', flush=True)
    (OUT/'tests.json').write_text(json.dumps(RECORDS,ensure_ascii=False,indent=2),encoding='utf-8')
    artifacts = {
        'MODIFIED_FILE':OUT/'payload/video/A1S01P01_RU.srt',
        'DIFF_FILE':OUT/'DIFF_FILE.diff',
        'VERIFICATION':OUT/'VERIFICATION.txt',
        'ROLLBACK':OUT/'ROLLBACK.sh',
    }
    lines=['FMV PROBE VERIFIED 2026-09-25',
           'CHANGED FIELD: six SRT cue text lines; custom v12 carrier; cue numbers and timestamps unchanged.',
           'No POD/DLL/EXE/BIK changes and no game launch.',
           'Visual subtitle placement and audio synchronization: pending user in-game test.',
           'Native emulation scope: raw line reader 0x64CE30 and wrapper 0x4E5A90/0x4E58C0.',
           'Width/isspace/getc/memset boundaries are fixture stubs; renderer and Bink are not executed.',
           'Static call chain: SRT name 0x68E222; raw text read 0x68E32A; wrap 0x68EB00; centered draw 0x68EB85 -> 0x4E6D10 -> 0x4E6BE0 -> 0x4E6AB0 (existing v12 hook).',
           'Original hash: '+m['original_sha256'],
           'Modified hash: '+m['payload_sha256'],
           'ROLLBACK restored original bytes and existing-subtitle status on isolated copy.',
           'ROLLBACK no-original test restored absence; later user-edit guard passed.',
           'MODIFIED_FILE remains compiled Chinese; actual installed SRT remains user original.']
    lines.extend(f'{k}: {p}' for k,p in artifacts.items())
    for r in RECORDS:
        lines.extend(['',r['label'],'COMMAND: '+r['command'],'INPUT: '+r['input'],'LITERAL STDOUT:',r['stdout'],'LITERAL STDERR:',r['stderr'],'EXIT: '+str(r['exit'])])
    lines.extend(['','LIVE FILES UNCHANGED: PASS',json.dumps(before,indent=2)])
    artifacts['VERIFICATION'].write_text('\n'.join(lines)+'\n',encoding='utf-8')
    archive=OUT/'BloodRayne2_FMV_Opening_Probe.zip'
    files = [p for p in OUT.rglob('*') if p.is_file() and p != archive and p.name!='sha256.json']
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in files:
            z.write(p,str(p.relative_to(ROOT)))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for p in files: assert z.read(str(p.relative_to(ROOT)).replace('\\','/'))==p.read_bytes()
    digest={str(p.relative_to(OUT)):sha(p) for p in files+[archive]}
    (OUT/'sha256.json').write_text(json.dumps(digest,indent=2),encoding='utf-8')
    # Reopen all published artifacts, scripts, source and package members.
    for p in files+[archive,OUT/'sha256.json']:
        assert p.read_bytes()
    print('REOPEN_ALL_AND_ZIP: PASS',flush=True)
    print('READY '+str(archive),flush=True)

if __name__=='__main__': main()
