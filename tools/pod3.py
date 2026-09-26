from __future__ import annotations

import argparse
import hashlib
import struct
from dataclasses import dataclass
from pathlib import Path


POD3_MAGIC = b"POD3"
ENTRY_SIZE = 20


def crc32_mpeg2(data: bytes) -> int:
    crc = 0xFFFFFFFF
    poly = 0x04C11DB7
    for byte in data:
        crc ^= byte << 24
        for _ in range(8):
            if crc & 0x80000000:
                crc = ((crc << 1) & 0xFFFFFFFF) ^ poly
            else:
                crc = (crc << 1) & 0xFFFFFFFF
    return crc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


@dataclass(frozen=True)
class PodEntry:
    index: int
    record_offset: int
    name: str
    size: int
    offset: int
    timestamp: int
    checksum: int


class Pod3:
    def __init__(self, data: bytes):
        self.data = data
        if data[:4] != POD3_MAGIC:
            raise ValueError("Not a POD3 archive")
        if len(data) < 0x114:
            raise ValueError("POD3 header is truncated")

        self.entry_count = struct.unpack_from("<I", data, 0x58)[0]
        self.entry_offset = struct.unpack_from("<I", data, 0x108)[0]
        self.names_size = struct.unpack_from("<I", data, 0x110)[0]
        self.names_offset = self.entry_offset + self.entry_count * ENTRY_SIZE
        self.names_end = self.names_offset + self.names_size
        if self.names_end > len(data):
            raise ValueError("POD3 name table is out of range")

        entries: list[PodEntry] = []
        for index in range(self.entry_count):
            record_offset = self.entry_offset + index * ENTRY_SIZE
            if record_offset + ENTRY_SIZE > len(data):
                raise ValueError(f"POD3 entry table is truncated at {index}")
            name_offset, size, offset, timestamp, checksum = struct.unpack_from(
                "<IIIII", data, record_offset
            )
            name_start = self.names_offset + name_offset
            name_end = data.find(b"\0", name_start, self.names_end)
            if name_start < self.names_offset or name_end < 0:
                raise ValueError(f"Invalid name for POD3 entry {index}")
            name = data[name_start:name_end].decode("ascii")
            if offset + size > len(data):
                raise ValueError(f"POD3 entry data is out of range: {name}")
            entries.append(
                PodEntry(
                    index=index,
                    record_offset=record_offset,
                    name=name,
                    size=size,
                    offset=offset,
                    timestamp=timestamp,
                    checksum=checksum,
                )
            )
        self.entries = entries
        self.by_name = {entry.name: entry for entry in entries}
        if len(self.by_name) != len(entries):
            raise ValueError("POD3 archive contains duplicate names")

    @classmethod
    def read(cls, path: Path) -> "Pod3":
        return cls(path.read_bytes())

    def read_entry(self, name: str) -> bytes:
        entry = self.by_name[name]
        return self.data[entry.offset : entry.offset + entry.size]

    def verify_crcs(self) -> list[str]:
        failures: list[str] = []
        for entry in self.entries:
            blob = self.read_entry(entry.name)
            actual = crc32_mpeg2(blob)
            if actual != entry.checksum:
                failures.append(
                    f"{entry.name}: stored={entry.checksum:08X} actual={actual:08X}"
                )
        return failures


class Pod3File:
    """Streaming POD3 reader for large archives such as W32ART.POD."""

    def __init__(self, path: Path):
        self.path = path
        self.file_size = path.stat().st_size
        with path.open("rb") as stream:
            header = stream.read(0x114)
            if header[:4] != POD3_MAGIC:
                raise ValueError("Not a POD3 archive")
            if len(header) < 0x114:
                raise ValueError("POD3 header is truncated")

            self.entry_count = struct.unpack_from("<I", header, 0x58)[0]
            self.entry_offset = struct.unpack_from("<I", header, 0x108)[0]
            self.names_size = struct.unpack_from("<I", header, 0x110)[0]
            self.names_offset = self.entry_offset + self.entry_count * ENTRY_SIZE
            self.names_end = self.names_offset + self.names_size
            if self.names_end > self.file_size:
                raise ValueError("POD3 name table is out of range")

            stream.seek(self.entry_offset)
            entry_table = stream.read(self.entry_count * ENTRY_SIZE)
            if len(entry_table) != self.entry_count * ENTRY_SIZE:
                raise ValueError("POD3 entry table is truncated")
            names = stream.read(self.names_size)
            if len(names) != self.names_size:
                raise ValueError("POD3 name table is truncated")

        entries: list[PodEntry] = []
        for index in range(self.entry_count):
            record_offset = self.entry_offset + index * ENTRY_SIZE
            table_offset = index * ENTRY_SIZE
            name_offset, size, offset, timestamp, checksum = struct.unpack_from(
                "<IIIII", entry_table, table_offset
            )
            name_end = names.find(b"\0", name_offset)
            if name_offset >= len(names) or name_end < 0:
                raise ValueError(f"Invalid name for POD3 entry {index}")
            name = names[name_offset:name_end].decode("ascii")
            if offset + size > self.file_size:
                raise ValueError(f"POD3 entry data is out of range: {name}")
            entries.append(
                PodEntry(
                    index=index,
                    record_offset=record_offset,
                    name=name,
                    size=size,
                    offset=offset,
                    timestamp=timestamp,
                    checksum=checksum,
                )
            )
        self.entries = entries
        self.by_name = {entry.name: entry for entry in entries}
        if len(self.by_name) != len(entries):
            raise ValueError("POD3 archive contains duplicate names")

    def read_entry(self, name: str) -> bytes:
        entry = self.by_name[name]
        with self.path.open("rb") as stream:
            stream.seek(entry.offset)
            blob = stream.read(entry.size)
        if len(blob) != entry.size:
            raise ValueError(f"POD3 entry data is truncated: {name}")
        return blob

    def verify_crcs(self) -> list[str]:
        failures: list[str] = []
        for entry in self.entries:
            blob = self.read_entry(entry.name)
            actual = crc32_mpeg2(blob)
            if actual != entry.checksum:
                failures.append(
                    f"{entry.name}: stored={entry.checksum:08X} actual={actual:08X}"
                )
        return failures


def patch_entries_fixed_capacity(
    source: bytes, replacements: dict[str, bytes]
) -> bytes:
    pod = Pod3(source)
    patched = bytearray(source)
    for name, blob in replacements.items():
        entry = pod.by_name[name]
        if len(blob) > entry.size:
            raise ValueError(
                f"Replacement exceeds fixed capacity for {name}: "
                f"{len(blob)} > {entry.size}"
            )
        start = entry.offset
        old_end = start + entry.size
        patched[start : start + len(blob)] = blob
        patched[start + len(blob) : old_end] = b"\0" * (entry.size - len(blob))
        struct.pack_into("<I", patched, entry.record_offset + 4, len(blob))
        struct.pack_into(
            "<I", patched, entry.record_offset + 16, crc32_mpeg2(blob)
        )
    result = bytes(patched)
    if len(result) != len(source):
        raise AssertionError("Fixed-capacity patch changed POD size")
    return result


def add_entries(
    source: bytes,
    additions: dict[str, bytes],
    *,
    alignment: int = 16,
    timestamp: int = 0,
) -> bytes:
    """Append new data and rebuild the POD3 directory without moving old data."""
    if alignment <= 0 or alignment & (alignment - 1):
        raise ValueError("POD3 alignment must be a positive power of two")
    pod = Pod3(source)
    if not additions:
        return source
    duplicate_names = sorted(set(additions) & set(pod.by_name))
    if duplicate_names:
        raise ValueError(f"POD3 entries already exist: {duplicate_names}")

    old_names = source[pod.names_offset : pod.names_end]
    trailing = source[pod.names_end :]
    result = bytearray(source[: pod.entry_offset])
    new_records: list[tuple[int, int, int, int, int]] = []
    names = bytearray(old_names)

    for name, blob in additions.items():
        name_bytes = name.encode("ascii")
        if b"\0" in name_bytes:
            raise ValueError(f"POD3 entry name contains NUL: {name!r}")
        padding = (-len(result)) & (alignment - 1)
        if padding:
            result.extend(b"\0" * padding)
        data_offset = len(result)
        result.extend(blob)
        name_offset = len(names)
        names.extend(name_bytes + b"\0")
        new_records.append(
            (
                name_offset,
                len(blob),
                data_offset,
                timestamp,
                crc32_mpeg2(blob),
            )
        )

    entry_offset = len(result)
    old_table = source[pod.entry_offset : pod.names_offset]
    table = bytearray(old_table)
    for record in new_records:
        table.extend(struct.pack("<IIIII", *record))
    directory = bytes(table) + bytes(names)
    result.extend(directory)
    result.extend(trailing)

    struct.pack_into("<I", result, 0x58, pod.entry_count + len(additions))
    struct.pack_into("<I", result, 0x108, entry_offset)
    struct.pack_into("<I", result, 0x10C, crc32_mpeg2(directory))
    struct.pack_into("<I", result, 0x110, len(names))

    rebuilt = bytes(result)
    check = Pod3(rebuilt)
    if check.entry_count != pod.entry_count + len(additions):
        raise AssertionError("POD3 added-entry count mismatch")
    for entry in pod.entries:
        if check.read_entry(entry.name) != pod.read_entry(entry.name):
            raise AssertionError(f"POD3 existing entry changed: {entry.name}")
    for name, blob in additions.items():
        if check.read_entry(name) != blob:
            raise AssertionError(f"POD3 added entry mismatch: {name}")
    return rebuilt


def rebuild_entries(
    source: bytes,
    replacements: dict[str, bytes],
    additions: dict[str, bytes] | None = None,
    *,
    alignment: int = 16,
    timestamp: int = 0,
) -> bytes:
    """Rebuild the directory while appending arbitrary-size replacements.

    Existing resource data is retained byte-for-byte.  Replaced and newly
    added resources are appended before a rebuilt directory, so a replacement
    is not constrained by the old entry's physical slot.
    """
    if alignment <= 0 or alignment & (alignment - 1):
        raise ValueError("POD3 alignment must be a positive power of two")
    additions = {} if additions is None else additions
    pod = Pod3(source)
    missing = sorted(set(replacements) - set(pod.by_name))
    if missing:
        raise ValueError(f"POD3 replacement entries do not exist: {missing}")
    duplicate_names = sorted(set(additions) & set(pod.by_name))
    if duplicate_names:
        raise ValueError(f"POD3 entries already exist: {duplicate_names}")
    overlap = sorted(set(replacements) & set(additions))
    if overlap:
        raise ValueError(f"POD3 replace/add overlap: {overlap}")

    result = bytearray(source[: pod.entry_offset])
    records: list[tuple[int, int, int, int, int]] = []
    names = bytearray()

    def append_blob(blob: bytes) -> int:
        padding = (-len(result)) & (alignment - 1)
        if padding:
            result.extend(b"\0" * padding)
        offset = len(result)
        result.extend(blob)
        return offset

    for entry in pod.entries:
        name_offset = len(names)
        names.extend(entry.name.encode("ascii") + b"\0")
        if entry.name in replacements:
            blob = replacements[entry.name]
            offset = append_blob(blob)
            records.append(
                (
                    name_offset,
                    len(blob),
                    offset,
                    entry.timestamp,
                    crc32_mpeg2(blob),
                )
            )
        else:
            records.append(
                (
                    name_offset,
                    entry.size,
                    entry.offset,
                    entry.timestamp,
                    entry.checksum,
                )
            )

    for name, blob in additions.items():
        name_bytes = name.encode("ascii")
        if b"\0" in name_bytes:
            raise ValueError(f"POD3 entry name contains NUL: {name!r}")
        name_offset = len(names)
        names.extend(name_bytes + b"\0")
        offset = append_blob(blob)
        records.append(
            (
                name_offset,
                len(blob),
                offset,
                timestamp,
                crc32_mpeg2(blob),
            )
        )

    entry_offset = len(result)
    table = b"".join(struct.pack("<IIIII", *record) for record in records)
    directory = table + bytes(names)
    result.extend(directory)
    result.extend(source[pod.names_end :])
    struct.pack_into("<I", result, 0x58, len(records))
    struct.pack_into("<I", result, 0x108, entry_offset)
    struct.pack_into("<I", result, 0x10C, crc32_mpeg2(directory))
    struct.pack_into("<I", result, 0x110, len(names))

    rebuilt = bytes(result)
    check = Pod3(rebuilt)
    if check.entry_count != len(records):
        raise AssertionError("POD3 rebuilt entry count mismatch")
    for entry in pod.entries:
        expected = replacements.get(entry.name, pod.read_entry(entry.name))
        if check.read_entry(entry.name) != expected:
            raise AssertionError(f"POD3 rebuilt entry mismatch: {entry.name}")
    for name, blob in additions.items():
        if check.read_entry(name) != blob:
            raise AssertionError(f"POD3 added entry mismatch: {name}")
    return rebuilt


def extract_command(args: argparse.Namespace) -> None:
    pod = Pod3File(args.pod)
    wanted = [pattern.lower() for pattern in args.pattern]
    count = 0
    for entry in pod.entries:
        if wanted and not any(pattern in entry.name.lower() for pattern in wanted):
            continue
        target = args.out / Path(entry.name.replace("\\", "/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(pod.read_entry(entry.name))
        count += 1
    print(f"Extracted {count} entries to {args.out}")


def list_command(args: argparse.Namespace) -> None:
    pod = Pod3File(args.pod)
    wanted = [pattern.lower() for pattern in args.pattern]
    for entry in pod.entries:
        if wanted and not any(pattern in entry.name.lower() for pattern in wanted):
            continue
        print(
            f"{entry.index:5d} {entry.size:10d} {entry.offset:10d} "
            f"{entry.checksum:08X} {entry.name}"
        )


def verify_command(args: argparse.Namespace) -> None:
    pod = Pod3File(args.pod)
    failures = pod.verify_crcs()
    if failures:
        for failure in failures:
            print(failure)
        raise SystemExit(f"CRC verification failed for {len(failures)} entries")
    print(
        f"OK: {args.pod} | entries={pod.entry_count} | "
        f"sha256={sha256_file(args.pod)}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BloodRayne POD3 helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("pod", type=Path)
    list_parser.add_argument("pattern", nargs="*")
    list_parser.set_defaults(func=list_command)

    extract_parser = subparsers.add_parser("extract")
    extract_parser.add_argument("pod", type=Path)
    extract_parser.add_argument("out", type=Path)
    extract_parser.add_argument("pattern", nargs="*")
    extract_parser.set_defaults(func=extract_command)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("pod", type=Path)
    verify_parser.set_defaults(func=verify_command)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
