from pathlib import Path
import hashlib, json, shutil, zipfile

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
ROOT = PROJECT.parent
DIST = PROJECT / 'dist'
def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as s:
        for b in iter(lambda: s.read(1024*1024), b''): h.update(b)
    return h.hexdigest()
def main():
    files = [ROOT/'LANGUAGE.POD', ROOT/'dinput8.dll', *sorted((ROOT/'video').glob('*_RU.srt'))]
    assert len(files) == 17
    assert sha(files[0]) == '3f262cd2b6d69fed03344df1ba10e3fa4853b81249c6eda8bb428941773562d8'
    assert sha(files[1]) == 'd525cb5521fadc0373641e6cf7edbf988e5fb178ec65b61670cd85a5139a09dc'
    manifest = {'version':'1.0.0','date':'2026-09-30','game_sha256':sha(ROOT/'rayne2.exe'), 'files':[]}
    for p in files:
        rel = p.relative_to(ROOT).as_posix()
        dest = HERE/'payload'/rel
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(p,dest)
        manifest['files'].append({'path':rel,'sha256':sha(p),'bytes':p.stat().st_size})
        if p.suffix == '.srt': shutil.copy2(p,PROJECT/'video_subtitles'/p.name)
    (HERE/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    DIST.mkdir(exist_ok=True)
    archive = DIST/'BloodRayne2_CN_v1.0.0_20260930.zip'
    extra = ['manifest.json','manage.ps1','INSTALL.cmd','UNINSTALL.cmd','ROLLBACK.sh','README.zh-CN.txt']
    sums = '\n'.join(f"{f['sha256']}  payload/{f['path']}" for f in manifest['files'])+'\n'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for f in manifest['files']: z.write(HERE/'payload'/f['path'],'payload/'+f['path'])
        for name in extra: z.write(HERE/name,name)
        z.writestr('SHA256SUMS.txt',sums)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for f in manifest['files']: assert hashlib.sha256(z.read('payload/'+f['path'])).hexdigest()==f['sha256']
    shutil.copy2(archive,HERE/'MODIFIED_FILE.zip')
    (DIST/'BloodRayne2_CN_v1.0.0_20260930.sha256').write_text(sha(archive)+'  '+archive.name+'\n',encoding='ascii')
    print('RELEASE_OK payload_files=17 package_entries=24 hashes=all_valid crc=all_valid')
if __name__=='__main__': main()
