from pathlib import Path
import runpy
HERE=Path(__file__).resolve().parent
runpy.run_path(str(HERE/'releases/overlay-20260930/build.py'),run_name='__main__')
