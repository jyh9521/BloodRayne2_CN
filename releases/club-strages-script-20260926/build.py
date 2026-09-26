"""Insert boxed captions before the three audio-only ChitChat dbSay calls."""
from pathlib import Path
import hashlib
import struct
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "_cn_project" / "tools"))
from pod3 import Pod3, rebuild_entries

BASE_SHA = "1CC9A191D478AE87F97B454FD1D0419CE06A31709F8CB5B9D011D75EF83E3F18"
ENTRY = r"WORLD\A2_UNIONSTATION_PART3.SCB"
SAYS = [
    b"dbSay(a2s2_Severin_9.wav)",
    b"dbSay(a2s2_Rayne_26.wav)",
    b"dbSay(a2s2_Severin_10.wav)",
]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def split_scb(blob: bytes) -> list[bytes]:
    version, count, text_size = struct.unpack_from("<III", blob)
    assert version == 1 and len(blob) == 12 + text_size + count * 4
    body = blob[12:12 + text_size]
    assert body.endswith(b"\0")
    commands = body[:-1].split(b"\0")
    assert len(commands) == count
    source_lines = struct.unpack_from("<" + "I" * count, blob, 12 + text_size)
    assert source_lines == tuple(range(1, count + 1))
    return commands


def encode_scb(commands: list[bytes]) -> bytes:
    body = b"\0".join(commands) + b"\0"
    return (struct.pack("<III", 1, len(commands), len(body)) + body
            + struct.pack("<" + "I" * len(commands), *range(1, len(commands) + 1)))


def main() -> None:
    source = Pod3.read(ROOT / "COMMON.POD")
    assert digest(source.data) == BASE_SHA
    commands = split_scb(source.read_entry(ENTRY))
    first = commands.index(SAYS[0])
    assert commands[first-1:first+4] == [b":ChitChat", *SAYS, b"return"]
    replacement: list[bytes] = []
    for command in commands:
        if command in SAYS:
            replacement.append(command.replace(b"dbSay(", b"dbBoxedDisplay(", 1))
        replacement.append(command)
    assert len(replacement) == len(commands) + 3
    updated = encode_scb(replacement)
    assert split_scb(updated) == replacement
    result = Pod3(rebuild_entries(source.data, {ENTRY: updated}))
    assert result.entry_count == source.entry_count
    assert not result.verify_crcs()
    for entry in source.entries:
        if entry.name != ENTRY:
            assert result.read_entry(entry.name) == source.read_entry(entry.name)
    output = HERE / "payload" / "COMMON.POD"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(result.data)
    print(f"BUILD_OK entry={ENTRY} inserted_boxed_display=3 commands={len(replacement)} sha256={digest(result.data)}")


if __name__ == "__main__":
    main()
