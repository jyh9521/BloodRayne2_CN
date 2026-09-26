"""Static checks for the three Club Strages opening captions and x86 probe."""
from pathlib import Path
import struct
import sys

PROJECT = Path(__file__).resolve().parents[2]
GAME = PROJECT.parent
sys.path.insert(0, str(PROJECT / "tools"))
from pod3 import Pod3

pod = Pod3.read(GAME / "LANGUAGE.POD")
target = pod.read_entry(r"WORLD\RU\A2_UNIONSTATION_PART3.TXT")
samples = {
    b"a2s2_severin_9.wav": bytes.fromhex("82 b3 8c f2"),
    b"a2s2_rayne_26.wav": bytes.fromhex("8c fe 8f f0"),
    b"a2s2_severin_10.wav": bytes.fromhex("87 c4 8b fc"),
}
for key, prefix in samples.items():
    matches = [line for line in target.splitlines() if line.lower().startswith(key)]
    assert len(matches) == 1, (key, len(matches))
    assert matches[0].split(b",", 2)[2].lstrip().startswith(prefix), key

dll_path = Path(sys.argv[1]) if len(sys.argv) > 1 else GAME / "dinput8.dll"
dll = dll_path.read_bytes()
assert dll[:2] == b"MZ"
pe_offset = struct.unpack_from("<I", dll, 0x3C)[0]
assert dll[pe_offset:pe_offset + 4] == b"PE\0\0"
machine = struct.unpack_from("<H", dll, pe_offset + 4)[0]
assert machine == 0x14C, hex(machine)
print("CLUB_CAPTIONS keys=3 carrier_prefixes=3 proxy_machine=x86")
