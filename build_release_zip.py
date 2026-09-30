from pathlib import Path
import runpy, shutil
HERE=Path(__file__).resolve().parent
runpy.run_path(str(HERE/'releases/release-20260930/build.py'),run_name='__main__')
shutil.copy2(HERE/'dist/BloodRayne2_CN_v1.0.0_20260930.zip',HERE/'dist/BloodRayne2_CN_current.zip')
print('CURRENT_ALIAS_OK version=1.0.0')
