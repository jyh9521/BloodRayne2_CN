from pathlib import Path
import hashlib
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DIST = HERE / 'dist'
ARCHIVE = DIST / 'BloodRayne2_CN_current.zip'

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest().upper()

def main() -> None:
    inputs = [ROOT / 'LANGUAGE.POD', ROOT / 'dinput8.dll']
    inputs += sorted((ROOT / 'video').glob('*_RU.srt'))
    assert len(inputs) == 17, len(inputs)
    assert sha256(ROOT / 'LANGUAGE.POD') == '18B5FA66F69AD57327D91C54BFD08F3FD9DC34A7C76E15FF53FDBA22F8D35C97'
    assert sha256(ROOT / 'dinput8.dll') == '74BEEA7D2C91F71E142907EA4B26DB104B344D0F0EA6E7A325BE356BB17EF238'
    DIST.mkdir(exist_ok=True)
    sums = []
    with zipfile.ZipFile(ARCHIVE, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for path in inputs:
            name = path.relative_to(ROOT).as_posix()
            output.write(path, name)
            sums.append(f'{sha256(path)}  {name}')
        output.writestr('SHA256SUMS.txt', '\n'.join(sums) + '\n')
    (DIST / 'SHA256SUMS.txt').write_text('\n'.join(sums) + '\n', encoding='utf-8')
    print(f'RELEASE_OK files={len(inputs)} zip_sha256={sha256(ARCHIVE)} zip_bytes={ARCHIVE.stat().st_size}')

if __name__ == '__main__':
    main()
