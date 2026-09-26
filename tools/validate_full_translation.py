from __future__ import annotations

import csv
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path

from build_dbcs_probe import PAIR_RE, split_newline
from build_full_translation import (
    ATLAS_HEIGHT,
    ATLAS_WIDTH,
    BASELINE_COMMON,
    BASELINE_LANGUAGE,
    BUILD,
    CARRIER_CAPACITY,
    EXPECTED_COMMON_SHA256,
    EXPECTED_LANGUAGE_SHA256,
    EXPECTED_SOURCE_CREDITS_SHA256,
    GLYPH_HEIGHT,
    GLYPH_WIDTH,
    LEAD_MAX,
    LEAD_MIN,
    MOVELIST_NAME,
    MSGLIST_NAME,
    SOURCE_CREDITS_NAME,
    TAIL_COUNT,
    TAIL_MAX,
    TAIL_MIN,
    TARGET_CREDITS_NAME,
    TARGET_FNT_NAME,
    TARGET_TEX_NAME,
    build_dialogue_entries,
    build_movelist,
    build_msglist,
    choose_dialogue_text,
    load_dialogue_plan,
    load_menu_rows,
    load_move_rows,
    ordered_character_map,
)
from pod3 import Pod3, sha256_file
from tex_rgba import read_tex


ROOT = Path(__file__).resolve().parents[2]
PROXY = ROOT / "_cn_project" / "build" / "proxy" / "dinput8.dll"
EXE = ROOT / "rayne2.exe"
EXPECTED_EXE_SHA256 = (
    "EAE3925A344668500F3533EBEC146376C8B1BBDB168ED2C3B1D4DECB0ABF0952"
)


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream, dialect="excel-tab"))


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
        if virtual_address <= rva < (
            virtual_address + max(virtual_size, raw_size)
        ):
            return raw_offset + rva - virtual_address
    raise ValueError(f"RVA is not backed by a PE section: 0x{rva:X}")


def read_c_string(data: bytes, offset: int) -> str:
    end = data.index(b"\0", offset)
    return data[offset:end].decode("ascii")


def pe_exports(image: bytes) -> tuple[int, set[str]]:
    pe_offset = struct.unpack_from("<I", image, 0x3C)[0]
    machine = struct.unpack_from("<H", image, pe_offset + 4)[0]
    optional_offset = pe_offset + 24
    export_rva = struct.unpack_from("<I", image, optional_offset + 96)[0]
    export_offset = rva_to_file_offset(image, export_rva)
    fields = struct.unpack_from("<IIHHIIIIIII", image, export_offset)
    name_count = fields[7]
    name_table_offset = rva_to_file_offset(image, fields[9])
    names = set()
    for index in range(name_count):
        name_rva = struct.unpack_from(
            "<I", image, name_table_offset + index * 4
        )[0]
        names.add(read_c_string(image, rva_to_file_offset(image, name_rva)))
    return machine, names


def load_carrier_map() -> tuple[dict[bytes, str], dict[str, int]]:
    rows = read_tsv(BUILD / "character_map.tsv")
    by_pair: dict[bytes, str] = {}
    by_character: dict[str, int] = {}
    for row in rows:
        pair = bytes.fromhex(row["carrier"])
        index = int(row["atlas_index"])
        if pair in by_pair or row["character"] in by_character:
            raise ValueError("Character map contains a duplicate")
        lead, tail = pair
        if not LEAD_MIN <= lead <= LEAD_MAX:
            raise ValueError(f"Carrier lead is out of range: {pair.hex()}")
        if not TAIL_MIN <= tail <= TAIL_MAX:
            raise ValueError(f"Carrier tail is out of range: {pair.hex()}")
        expected_index = (
            (lead - LEAD_MIN) * TAIL_COUNT + tail - TAIL_MIN
        )
        if index != expected_index:
            raise ValueError(
                f"Carrier/index mismatch: {pair.hex()} != {index}"
            )
        by_pair[pair] = row["character"]
        by_character[row["character"]] = index
    return by_pair, by_character


def decode_carrier(data: bytes, by_pair: dict[bytes, str]) -> str:
    result: list[str] = []
    cursor = 0
    while cursor < len(data):
        value = data[cursor]
        if value < 0x80:
            result.append(chr(value))
            cursor += 1
            continue
        if cursor + 1 >= len(data):
            raise ValueError(f"Truncated carrier at byte {cursor}")
        pair = data[cursor : cursor + 2]
        if pair not in by_pair:
            raise ValueError(
                f"Unknown or stray high-byte carrier: {pair.hex().upper()}"
            )
        result.append(by_pair[pair])
        cursor += 2
    return "".join(result)


def parse_fnt(data: bytes) -> tuple[list[bytes], dict[int, bytes]]:
    preamble: list[bytes] = []
    rows: dict[int, bytes] = {}
    for line in data.splitlines():
        if len(line) >= 2 and line[1:2] == b":":
            rows[line[0]] = line
        else:
            preamble.append(line)
    return preamble, rows


def main() -> None:
    if sha256_file(BASELINE_LANGUAGE) != EXPECTED_LANGUAGE_SHA256:
        raise ValueError("Baseline LANGUAGE.POD hash mismatch")
    if sha256_file(BASELINE_COMMON) != EXPECTED_COMMON_SHA256:
        raise ValueError("COMMON.POD hash mismatch")
    if sha256_file(EXE) != EXPECTED_EXE_SHA256:
        raise ValueError("rayne2.exe hash mismatch")

    manifest = json.loads(
        (BUILD / "manifest.json").read_text(encoding="utf-8")
    )
    if manifest["language_sha256"] != sha256_file(
        BUILD / "LANGUAGE.POD"
    ):
        raise ValueError("Manifest LANGUAGE.POD hash mismatch")
    if not manifest["archive"]["requires_dynamic_glyph_patch"]:
        raise ValueError("Manifest does not require dynamic glyph patch")

    baseline = Pod3.read(BASELINE_LANGUAGE)
    common = Pod3.read(BASELINE_COMMON)
    built = Pod3.read(BUILD / "LANGUAGE.POD")
    if built.verify_crcs():
        raise ValueError("Built LANGUAGE.POD has CRC failures")
    additions = set(built.by_name) - set(baseline.by_name)
    if additions != {TARGET_TEX_NAME, TARGET_FNT_NAME}:
        raise ValueError(f"Unexpected added resources: {sorted(additions)}")
    expected_changed = set(manifest["changed_existing_entries"])
    actual_changed = {
        entry.name
        for entry in baseline.entries
        if built.read_entry(entry.name) != baseline.read_entry(entry.name)
    }
    if actual_changed != expected_changed:
        raise ValueError(
            "Changed resource set differs from manifest: "
            f"missing={sorted(expected_changed - actual_changed)[:5]} "
            f"extra={sorted(actual_changed - expected_changed)[:5]}"
        )

    credits = common.read_entry(SOURCE_CREDITS_NAME)
    if (
        hashlib.sha256(credits).hexdigest().upper()
        != EXPECTED_SOURCE_CREDITS_SHA256
    ):
        raise ValueError("English credits source hash mismatch")
    if built.read_entry(TARGET_CREDITS_NAME) != credits:
        raise ValueError("Credits are not the exact English fallback")

    by_pair, character_indexes = load_carrier_map()
    if len(by_pair) != manifest["carrier"]["glyphs_used"]:
        raise ValueError("Character-map count differs from manifest")
    if len(by_pair) > CARRIER_CAPACITY:
        raise ValueError("Character map exceeds carrier capacity")

    menu_rows = load_menu_rows()
    move_rows = load_move_rows()
    occurrences, source_by_id, unique_by_id = load_dialogue_plan()
    expected_texts = [
        row["translation_zh"] for row in menu_rows if row["translation_zh"]
    ]
    expected_texts.extend(row["translation_zh"] for row in move_rows)
    expected_texts.extend(
        choose_dialogue_text(
            occurrence, source_by_id, unique_by_id
        )[0]
        for occurrence in occurrences
    )
    expected_mapping = ordered_character_map(expected_texts)
    if expected_mapping != character_indexes:
        raise ValueError("Character map does not match current translations")

    expected_menu = build_msglist(
        baseline.read_entry(MSGLIST_NAME),
        menu_rows,
        expected_mapping,
    )
    if built.read_entry(MSGLIST_NAME) != expected_menu:
        raise ValueError("Built menu bytes differ from current menu.tsv")
    expected_moves = build_movelist(
        baseline.read_entry(MOVELIST_NAME),
        move_rows,
        expected_mapping,
    )
    if built.read_entry(MOVELIST_NAME) != expected_moves:
        raise ValueError("Built move-list bytes differ from current moves.tsv")
    expected_dialogue, modes = build_dialogue_entries(
        baseline,
        occurrences,
        source_by_id,
        unique_by_id,
        expected_mapping,
    )
    for name, blob in expected_dialogue.items():
        if built.read_entry(name) != blob:
            raise ValueError(f"Built dialogue differs: {name}")
    if dict(sorted(modes.items())) != manifest["translations"]["dialogue_modes"]:
        raise ValueError("Dialogue import-mode counts differ from manifest")

    maximum_distinct = 0
    maximum_label = ""
    for match in PAIR_RE.finditer(built.read_entry(MSGLIST_NAME)):
        decoded = decode_carrier(match.group(2), by_pair)
        count = len({character for character in decoded if ord(character) >= 128})
        if count > maximum_distinct:
            maximum_distinct = count
            maximum_label = "menu"
    for line_number, line in enumerate(
        built.read_entry(MOVELIST_NAME).splitlines(), start=1
    ):
        if line_number not in {int(row["line"]) for row in move_rows}:
            continue
        decoded = decode_carrier(line, by_pair)
        count = len({character for character in decoded if ord(character) >= 128})
        if count > maximum_distinct:
            maximum_distinct = count
            maximum_label = f"moves:{line_number}"
    for name, blob in expected_dialogue.items():
        for line in blob.splitlines():
            columns = line.split(b",", 2)
            if len(columns) != 3:
                continue
            decoded = decode_carrier(columns[2], by_pair)
            count = len(
                {character for character in decoded if ord(character) >= 128}
            )
            if count > maximum_distinct:
                maximum_distinct = count
                maximum_label = name
    if maximum_distinct > TAIL_COUNT:
        raise ValueError(
            f"One draw needs {maximum_distinct} dynamic glyphs: {maximum_label}"
        )

    source_fnt = (
        ROOT
        / "_cn_project"
        / "source"
        / "w32art_fonts"
        / "DATA"
        / "GOTHICTITLE_RU.FNT"
    ).read_bytes()
    built_fnt = built.read_entry(TARGET_FNT_NAME)
    _, source_fnt_rows = parse_fnt(source_fnt)
    _, built_fnt_rows = parse_fnt(built_fnt)
    for value in range(0x21, 0x80):
        if built_fnt_rows.get(value) != source_fnt_rows.get(value):
            raise ValueError(f"Printable ASCII FNT row changed: 0x{value:02X}")
    leaked_leads = [
        value
        for value in range(LEAD_MIN, LEAD_MAX + 1)
        if value in built_fnt_rows
    ]
    if leaked_leads:
        raise ValueError(f"Carrier leads have glyphs: {leaked_leads}")
    for value in range(TAIL_MIN, TAIL_MAX + 1):
        fields = built_fnt_rows[value].split(b":", 1)[1].strip().split(b",")
        if [int(item) for item in fields[2:4]] != [
            GLYPH_WIDTH,
            GLYPH_HEIGHT,
        ]:
            raise ValueError(f"Carrier tail metrics differ: 0x{value:02X}")

    tex_header, tex_image = read_tex(
        BUILD / manifest["targets"][TARGET_TEX_NAME]["path"]
    )
    del tex_header
    if tex_image.size != (ATLAS_WIDTH, ATLAS_HEIGHT):
        raise ValueError(f"Unexpected font atlas size: {tex_image.size}")
    if built.read_entry(TARGET_TEX_NAME) != (
        BUILD / manifest["targets"][TARGET_TEX_NAME]["path"]
    ).read_bytes():
        raise ValueError("Embedded TEX differs from build asset")
    if built.read_entry(TARGET_FNT_NAME) != (
        BUILD / manifest["targets"][TARGET_FNT_NAME]["path"]
    ).read_bytes():
        raise ValueError("Embedded FNT differs from build asset")

    exe = EXE.read_bytes()
    draw_offset = rva_to_file_offset(exe, 0xE6AB0)
    if exe[draw_offset : draw_offset + 6] != bytes.fromhex(
        "55 8B EC 8B 45 18"
    ):
        raise ValueError("CBitFont draw detour signature mismatch")
    proxy = PROXY.read_bytes()
    if manifest["proxy_sha256"] != sha256_file(PROXY):
        raise ValueError("Proxy does not match the release manifest")
    machine, exports = pe_exports(proxy)
    expected_exports = {
        "DirectInput8Create",
        "DllCanUnloadNow",
        "DllGetClassObject",
        "DllRegisterServer",
        "DllUnregisterServer",
        "GetdfDIJoystick",
    }
    if machine != 0x14C or exports != expected_exports:
        raise ValueError("Proxy architecture/export mismatch")
    for marker in [
        b"dynamic_font=%s",
        b"font_archive=%s",
    ]:
        if marker not in proxy:
            raise ValueError(f"Proxy lacks marker: {marker!r}")
    if b"W32RUSND.POD" in proxy:
        raise ValueError("Abandoned sound archive redirect found in proxy")

    report = {
        "build_id": manifest["build_id"],
        "language_sha256": sha256_file(BUILD / "LANGUAGE.POD"),
        "language_entries": built.entry_count,
        "changed_existing_entries": len(actual_changed),
        "added_entries": sorted(additions),
        "menu_rows": len(menu_rows),
        "move_rows": len(move_rows),
        "dialogue_occurrences": len(occurrences),
        "dialogue_modes": dict(sorted(modes.items())),
        "dynamic_glyphs": len(by_pair),
        "carrier_capacity": CARRIER_CAPACITY,
        "per_draw_capacity": TAIL_COUNT,
        "maximum_distinct_in_one_draw": maximum_distinct,
        "maximum_distinct_location": maximum_label,
        "proxy_sha256": sha256_file(PROXY),
        "proxy_machine": "x86",
        "credits": "byte-exact English fallback",
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
