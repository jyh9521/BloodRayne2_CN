from __future__ import annotations

import csv
import hashlib
import json
import re
import struct
import sys
from collections import Counter
from pathlib import Path

from pod3 import Pod3, Pod3File, sha256_file


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "_cn_project"
BASELINE_LANGUAGE = PROJECT / "baseline" / "LANGUAGE.POD"
BUILT_LANGUAGE = PROJECT / "build" / "menu_probe" / "LANGUAGE.POD"
MANIFEST = PROJECT / "build" / "menu_probe" / "manifest.json"
EXTRACTED = PROJECT / "translation" / "extracted"
CATALOG = PROJECT / "translation" / "catalog.tsv"
EXE = ROOT / "rayne2.exe"
PROXY = PROJECT / "build" / "proxy" / "dinput8.dll"
EXPECTED_EXE_SHA256 = (
    "EAE3925A344668500F3533EBEC146376C8B1BBDB168ED2C3B1D4DECB0ABF0952"
)
TARGETS = {
    r"ART\GOTHICTITLE_RU.TEX",
    r"DATA\GOTHICTITLE_RU.FNT",
}
ORIGINAL_ORDER = [
    "W32ART.POD",
    "W32MODEL.POD",
    "W32SET.POD",
    "W32SOUND.POD",
    "LANGUAGE.POD",
    "COMMON.POD",
    "W32ART2.POD",
    "W32ART3.POD",
]
PATCHED_ORDER = [
    "LANGUAGE.POD",
    "W32MODEL.POD",
    "W32SET.POD",
    "W32SOUND.POD",
    "W32ART.POD",
    "COMMON.POD",
    "W32ART2.POD",
    "W32ART3.POD",
]
TAG_RE = re.compile(r"@@[^@]+@@")


def rva_to_file_offset(image: bytes, rva: int) -> int:
    pe_offset = struct.unpack_from("<I", image, 0x3C)[0]
    section_count = struct.unpack_from("<H", image, pe_offset + 6)[0]
    optional_size = struct.unpack_from("<H", image, pe_offset + 20)[0]
    section_offset = pe_offset + 24 + optional_size
    for index in range(section_count):
        offset = section_offset + index * 40
        virtual_size, virtual_address, raw_size, raw_offset = (
            struct.unpack_from("<IIII", image, offset + 8)
        )
        span = max(virtual_size, raw_size)
        if virtual_address <= rva < virtual_address + span:
            return raw_offset + rva - virtual_address
    raise ValueError(f"RVA is not backed by a PE section: 0x{rva:X}")


def read_c_string(data: bytes, offset: int) -> str:
    end = data.index(b"\0", offset)
    return data[offset:end].decode("ascii")


def pe_exports(image: bytes) -> tuple[int, set[str]]:
    pe_offset = struct.unpack_from("<I", image, 0x3C)[0]
    machine = struct.unpack_from("<H", image, pe_offset + 4)[0]
    optional_offset = pe_offset + 24
    if struct.unpack_from("<H", image, optional_offset)[0] != 0x10B:
        raise ValueError("Expected a PE32 optional header")
    export_rva = struct.unpack_from("<I", image, optional_offset + 96)[0]
    export_offset = rva_to_file_offset(image, export_rva)
    fields = struct.unpack_from("<IIHHIIIIIII", image, export_offset)
    name_count = fields[7]
    name_table_rva = fields[9]
    name_table_offset = rva_to_file_offset(image, name_table_rva)
    names = set()
    for index in range(name_count):
        name_rva = struct.unpack_from(
            "<I", image, name_table_offset + index * 4
        )[0]
        names.add(read_c_string(image, rva_to_file_offset(image, name_rva)))
    return machine, names


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream, dialect="excel-tab"))


def main() -> None:
    if sha256_file(EXE) != EXPECTED_EXE_SHA256:
        raise ValueError("rayne2.exe hash mismatch")
    image = EXE.read_bytes()
    pe_offset = struct.unpack_from("<I", image, 0x3C)[0]
    image_base = struct.unpack_from("<I", image, pe_offset + 24 + 28)[0]
    push_offset = rva_to_file_offset(image, 0x1A4B68)
    literal_offset = rva_to_file_offset(image, 0x3106C4)
    opcode, operand = struct.unpack_from("<BI", image, push_offset)
    if opcode != 0x68 or operand != image_base + 0x310694:
        raise ValueError("W32ART mount-format instruction mismatch")
    if image[literal_offset : literal_offset + 13] != b"LANGUAGE.POD\0":
        raise ValueError("LANGUAGE.POD mount literal mismatch")
    proxy_image = PROXY.read_bytes()
    machine, exports = pe_exports(proxy_image)
    expected_exports = {
        "DirectInput8Create",
        "DllCanUnloadNow",
        "DllGetClassObject",
        "DllRegisterServer",
        "DllUnregisterServer",
        "GetdfDIJoystick",
    }
    if machine != 0x14C or exports != expected_exports:
        raise ValueError(
            f"Proxy PE/export mismatch: machine=0x{machine:X} "
            f"exports={sorted(exports)}"
        )
    if b"font_archive=%s" not in proxy_image:
        raise ValueError("Proxy lacks language-first status marker")
    if b"W32RUSND.POD" in proxy_image:
        raise ValueError("Abandoned sound-archive redirect found in proxy")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    baseline = Pod3.read(BASELINE_LANGUAGE)
    built = Pod3.read(BUILT_LANGUAGE)
    if built.verify_crcs():
        raise ValueError("Built LANGUAGE.POD has CRC failures")
    if built.entry_count != baseline.entry_count + len(TARGETS):
        raise ValueError("Built LANGUAGE.POD entry count mismatch")
    if set(built.by_name) - set(baseline.by_name) != TARGETS:
        raise ValueError("Unexpected added LANGUAGE.POD entries")
    for entry in baseline.entries:
        if built.read_entry(entry.name) != baseline.read_entry(entry.name):
            if entry.name not in {
                r"WORLD\RU\MSGLIST.TXT",
                r"WORLD\RU\CREDITLIST.TXT",
                r"WORLD\RU\A1_MANSION_PART1.TXT",
            }:
                raise ValueError(
                    f"Unexpected existing LANGUAGE entry changed: {entry.name}"
                )
    for name in TARGETS:
        info = manifest["targets"][name]
        disk_blob = (MANIFEST.parent / info["path"]).read_bytes()
        if built.read_entry(name) != disk_blob:
            raise ValueError(f"Embedded font differs from build asset: {name}")

    archives: dict[str, set[str]] = {}
    for filename in ORIGINAL_ORDER:
        if filename == "LANGUAGE.POD":
            archives[filename] = set(baseline.by_name)
        else:
            archives[filename] = set(Pod3File(ROOT / filename).by_name)
    art_names = archives["W32ART.POD"]
    duplicate_counts = {}
    for filename, names in archives.items():
        if filename == "W32ART.POD":
            continue
        duplicates = art_names & names
        duplicate_counts[filename] = len(duplicates)
        if duplicates:
            raise ValueError(
                f"Clean W32ART has duplicate names with {filename}: "
                f"{sorted(duplicates)[:5]}"
            )

    patched_archives = dict(archives)
    patched_archives["LANGUAGE.POD"] = set(built.by_name)
    target_provider = {}
    for target in TARGETS:
        providers = [
            filename
            for filename in PATCHED_ORDER
            if target in patched_archives[filename]
        ]
        if not providers or providers[0] != "LANGUAGE.POD":
            raise ValueError(f"Language font does not win mount lookup: {target}")
        target_provider[target] = providers

    catalog_rows = read_tsv(CATALOG)
    split_rows = {
        path.stem: read_tsv(path)
        for path in sorted(EXTRACTED.glob("*.tsv"))
    }
    combined = [
        row
        for kind in ("dialogue", "menu", "moves", "credits")
        for row in split_rows[kind]
    ]
    if [row["id"] for row in combined] != [
        row["id"] for row in catalog_rows
    ]:
        raise ValueError("Split translation files do not reproduce catalog order")
    duplicate_ids = [
        row_id
        for row_id, count in Counter(
            row["id"] for row in catalog_rows
        ).items()
        if count != 1
    ]
    if duplicate_ids:
        raise ValueError(f"Duplicate extracted IDs: {duplicate_ids[:5]}")
    move_tag_mismatches = [
        row["id"]
        for row in split_rows["moves"]
        if sorted(TAG_RE.findall(row["source_en"])) != sorted(
            TAG_RE.findall(row["source_ru"])
        )
    ]
    for row in split_rows["moves"]:
        if (
            row["id"] in move_tag_mismatches
            and "use English structure" not in row["notes"]
        ):
            raise ValueError(
                f"Unmarked move-list tag mismatch: {row['id']}"
            )

    report = {
        "exe_sha256": sha256_file(EXE),
        "proxy_sha256": sha256_file(PROXY),
        "proxy_machine": "x86",
        "proxy_exports": sorted(exports),
        "clean_mount_order": ORIGINAL_ORDER,
        "patched_mount_order": PATCHED_ORDER,
        "clean_w32art_duplicate_counts": duplicate_counts,
        "font_providers_after_patch": target_provider,
        "language_sha256": sha256_file(BUILT_LANGUAGE),
        "language_entries": built.entry_count,
        "language_added_entries": sorted(TARGETS),
        "catalog_rows": len(catalog_rows),
        "catalog_by_kind": {
            kind: len(rows) for kind, rows in split_rows.items()
        },
        "move_en_ru_tag_mismatches": move_tag_mismatches,
        "catalog_sha256": hashlib.sha256(
            CATALOG.read_bytes()
        ).hexdigest().upper(),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise
