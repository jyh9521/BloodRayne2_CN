from pathlib import Path
import hashlib
import zipfile

HERE = Path(__file__).resolve().parent
ARCHIVE = HERE / 'dist/BloodRayne2_CN_current.zip'

def main() -> None:
    with zipfile.ZipFile(ARCHIVE) as package:
        records = package.read('SHA256SUMS.txt').decode('utf-8').splitlines()
        assert len(records) == 17, len(records)
        expected_names = set()
        for record in records:
            digest, name = record.split('  ', 1)
            actual = hashlib.sha256(package.read(name)).hexdigest().upper()
            assert actual == digest, name
            expected_names.add(name)
        assert expected_names == set(package.namelist()) - {'SHA256SUMS.txt'}
        assert package.testzip() is None
    print(f'ZIP_OK files={len(records)} crc=all_valid sha256=all_valid')

if __name__ == '__main__':
    main()
