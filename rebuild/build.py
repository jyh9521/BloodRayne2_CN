"""Portable source/resource rebuild; never reads an installed Chinese payload."""
from pathlib import Path
import argparse, hashlib, json, os, shutil, struct, subprocess, sys, zipfile

HERE=Path(__file__).resolve().parent
REPO=HERE.parent
sys.path.insert(0,str(REPO/'tools'))
import pod3

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def fast_crc(data):
    crc=0xffffffff
    for b in data: crc=((crc<<8)&0xffffffff)^CRC_TABLE[((crc>>24)^b)&255]
    return crc
CRC_TABLE=[]
for i in range(256):
    c=i<<24
    for _ in range(8): c=((c<<1)^0x04c11db7)&0xffffffff if c&0x80000000 else (c<<1)&0xffffffff
    CRC_TABLE.append(c)
assert fast_crc(b'123456789')==pod3.crc32_mpeg2(b'123456789')==0x0376e6e7
pod3.crc32_mpeg2=fast_crc

def compiler_env():
    env=dict(os.environ)
    if shutil.which('cl.exe'): return env
    vswhere=Path(os.environ.get('ProgramFiles(x86)',r'C:\Program Files (x86)'))/'Microsoft Visual Studio/Installer/vswhere.exe'
    root=subprocess.check_output([str(vswhere),'-latest','-products','*','-requires','Microsoft.VisualStudio.Component.VC.Tools.x86.x64','-property','installationPath'],text=True).strip()
    if not root: raise RuntimeError('Install Visual Studio Build Tools with Desktop development with C++ and Windows SDK.')
    vc=Path(root)/'Common7/Tools/VsDevCmd.bat'
    result=subprocess.check_output(f'cmd.exe /u /d /s /c ""{vc}" -no_logo -arch=x86 -host_arch=x64 >nul && set"').decode('utf-16le')
    for line in result.splitlines():
        if '=' in line and not line.startswith('='):
            k,v=line.split('=',1); env[k.upper()]=v
    return env

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-pod',type=Path,required=True,help='Pristine Steam LANGUAGE.POD')
    parser.add_argument('--output',type=Path,default=REPO/'build/reproducible')
    args=parser.parse_args()
    out=args.output.resolve(); out.mkdir(parents=True,exist_ok=True)
    m=json.loads((HERE/'assets/resources.json').read_text(encoding='utf-8'))
    if sha(args.base_pod)!=m['baseline_sha256']: raise RuntimeError('Pristine LANGUAGE.POD hash mismatch; input not changed.')
    base=pod3.Pod3.read(args.base_pod)
    assert len(base.entries)==m['baseline_entries']
    replacements={}; additions={}
    with zipfile.ZipFile(HERE/'assets/localized_resources.zip') as z:
        assert z.testzip() is None
        for r in m['resources']:
            data=z.read(r['member']); assert hashlib.sha256(data).hexdigest()==r['sha256']
            (additions if r['addition'] else replacements)[r['entry']]=data
    built=pod3.Pod3(pod3.rebuild_entries(base.data,replacements,additions))
    assert len(built.entries)==m['final_entries']
    assert {e.name:hashlib.sha256(built.read_entry(e.name)).hexdigest() for e in built.entries}==m['final_entry_hashes']
    assert not built.verify_crcs()
    package=out/'package'; payload=package/'payload'; payload.mkdir(parents=True,exist_ok=True)
    (payload/'LANGUAGE.POD').write_bytes(built.data)
    env=compiler_env()
    cl=shutil.which('cl.exe',path=env.get('Path',env.get('PATH')))
    assert cl, 'cl.exe not found after compiler setup'
    runtime=HERE/'runtime'
    command=[cl,'/nologo','/std:c++17','/O2','/MT','/EHsc','/LD','/Brepro',f'/Fo{out}{os.sep}',f'/Fe{payload / "dinput8.dll"}',str(runtime/'dinput8_cn.cpp'),'user32.lib','gdi32.lib','ole32.lib','/link',f'/DEF:{runtime / "dinput8.def"}']
    subprocess.run(command,env=env,cwd=out,check=True)
    blob=(payload/'dinput8.dll').read_bytes(); pe=struct.unpack_from('<I',blob,0x3c)[0]
    assert blob[:2]==b'MZ' and blob[pe:pe+4]==b'PE\0\0' and struct.unpack_from('<H',blob,pe+4)[0]==0x14c
    for export in ['DirectInput8Create','DllCanUnloadNow','DllGetClassObject','DllRegisterServer','DllUnregisterServer']:
        assert export.encode()+b'\0' in blob, export
    source_srt=sorted((REPO/'video_subtitles').glob('*_RU.srt')); assert len(source_srt)==15
    (payload/'video').mkdir(exist_ok=True)
    for p in source_srt: shutil.copy2(p,payload/'video'/p.name)
    files=[payload/'LANGUAGE.POD',payload/'dinput8.dll',*sorted((payload/'video').glob('*.srt'))]
    manifest={'version':'1.0.0-source-rebuild','game_sha256':m['game_sha256'],'files':[{'path':p.relative_to(payload).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in files]}
    (package/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    installer=REPO/'releases/release-20260930'
    for name in ['manage.ps1','INSTALL.cmd','UNINSTALL.cmd','ROLLBACK.sh','README.zh-CN.txt']: shutil.copy2(installer/name,package/name)
    archive=out/'BloodRayne2_CN_rebuilt.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in files: z.write(p,p.relative_to(package).as_posix())
        for name in ['manifest.json','manage.ps1','INSTALL.cmd','UNINSTALL.cmd','ROLLBACK.sh','README.zh-CN.txt']: z.write(package/name,name)
        z.writestr('SHA256SUMS.txt','\n'.join(f"{f['sha256']}  payload/{f['path']}" for f in manifest['files'])+'\n')
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for f in manifest['files']: assert hashlib.sha256(z.read('payload/'+f['path'])).hexdigest()==f['sha256']
    print('REBUILD_OK language_entries=393 entry_hashes=393 crc=all_valid dll=x86 exports=5 ru_srt=15 payload_files=17 package_crc=all_valid')
    print('OUTPUT '+str(archive))
if __name__=='__main__': main()
