from __future__ import annotations

import csv
import hashlib
import json
import re
import struct
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from build_dbcs_probe import MSGLIST_NAME, PAIR_RE, set_header, split_newline
from pod3 import Pod3, rebuild_entries, sha256_file
from tex_rgba import read_tex, write_tex


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "_cn_project"
TRANSLATION = PROJECT / "translation"
EXTRACTED = TRANSLATION / "extracted"
DEDUPLICATED = TRANSLATION / "dialogue_deduplicated"
BASELINE_LANGUAGE = PROJECT / "baseline" / "LANGUAGE.POD"
BASELINE_COMMON = ROOT / "COMMON.POD"
SOURCE_FONTS = PROJECT / "source" / "w32art_fonts"
BUILD = PROJECT / "build" / "full_translation"

EXPECTED_LANGUAGE_SHA256 = (
    "2E3E0797E147E58B7308D3FCEDBDF0A06CB433FB099FC24B8FB38943D8B358E4"
)
EXPECTED_COMMON_SHA256 = (
    "1CC9A191D478AE87F97B454FD1D0419CE06A31709F8CB5B9D011D75EF83E3F18"
)
BUILD_ID = "full-zh-v12-20260923"

SOURCE_TEX = SOURCE_FONTS / "ART" / "GOTHICTITLE_RU.TEX"
SOURCE_FNT = SOURCE_FONTS / "DATA" / "GOTHICTITLE_RU.FNT"
EXPECTED_SOURCE_TEX_SHA256 = (
    "D20F28E1BEEE40F849AE09A1B382F87C1CA60CEDB5FEBC6AFC4C11B4DE288D50"
)
EXPECTED_SOURCE_FNT_SHA256 = (
    "CA633E6E57EA2A39FBDAC1B8C7F6F430F09D003B44DA66BF4D648CC0156A1DE8"
)

CHINESE_FONT = Path(r"C:\Windows\Fonts\NotoSansSC-VF.ttf")
FONT_FACE = b"Noto Sans SC"
FONT_WEIGHT = 400
FONT_SIZE = 30
TARGET_TEX_NAME = r"ART\GOTHICTITLE_RU.TEX"
TARGET_FNT_NAME = r"DATA\GOTHICTITLE_RU.FNT"
MOVELIST_NAME = r"WORLD\RU\MOVELIST.TXT"
TARGET_CREDITS_NAME = r"WORLD\RU\CREDITLIST.TXT"
SOURCE_CREDITS_NAME = r"DATA\CREDITS.TXT"
EXPECTED_SOURCE_CREDITS_SHA256 = (
    "D8539B6D58F1B84FFAF325CB4610614EA7C0968CFA538DA17EC4C945CAD83079"
)

# The engine stores only 256 glyph records and normally indexes every byte
# separately.  The proxy turns each custom pair into a per-draw dynamic glyph.
# Lead and tail ranges must stay disjoint: leads remain zero-width, while every
# tail has a generic full-width record for layout before the draw hook runs.
LEAD_MIN = 0x81
LEAD_MAX = 0x9F
TAIL_MIN = 0xA1
TAIL_MAX = 0xFE
TAIL_COUNT = TAIL_MAX - TAIL_MIN + 1
CARRIER_CAPACITY = (LEAD_MAX - LEAD_MIN + 1) * TAIL_COUNT

ATLAS_WIDTH = 2048
ATLAS_HEIGHT = 4096
ATLAS_BASE_Y = 256
CELL_WIDTH = 34
ROW_PITCH = 39
GLYPH_WIDTH = 32
GLYPH_HEIGHT = 37
ATLAS_COLUMNS = ATLAS_WIDTH // CELL_WIDTH

TAG_RE = re.compile(r"@@[^@]+@@")
PLACEHOLDER_RE = re.compile(r"%(?:[-+0-9.]*[A-Za-z%])")


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream, dialect="excel-tab"))


def validate_unique_ids(rows: list[dict[str, str]], label: str) -> None:
    counts = Counter(row["id"] for row in rows)
    duplicates = sorted(row_id for row_id, count in counts.items() if count != 1)
    if duplicates:
        raise ValueError(f"{label} contains duplicate IDs: {duplicates[:5]}")


def validate_format_tokens(
    source: str, target: str, row_id: str, *, tags: bool
) -> None:
    source_placeholders = sorted(PLACEHOLDER_RE.findall(source))
    target_placeholders = sorted(PLACEHOLDER_RE.findall(target))
    if source_placeholders != target_placeholders:
        raise ValueError(
            f"Placeholder mismatch for {row_id}: "
            f"{source_placeholders!r} != {target_placeholders!r}"
        )
    if tags:
        source_tags = sorted(TAG_RE.findall(source))
        target_tags = sorted(TAG_RE.findall(target))
        if source_tags != target_tags:
            raise ValueError(
                f"Control-tag mismatch for {row_id}: "
                f"{source_tags!r} != {target_tags!r}"
            )


def load_menu_rows() -> list[dict[str, str]]:
    rows = read_tsv(EXTRACTED / "menu.tsv")
    validate_unique_ids(rows, "menu.tsv")
    translated = 0
    structural_blank = 0
    for row in rows:
        target = row["translation_zh"]
        if not target:
            if not row["source_en"] and not row["source_ru"]:
                structural_blank += 1
                continue
            raise ValueError(f"Untranslated menu row: {row['id']}")
        if '"' in target:
            raise ValueError(
                f"Menu translation contains an unescaped quote: {row['id']}"
            )
        validate_format_tokens(
            row["source_en"], target, row["id"], tags=True
        )
        translated += 1
    if translated != 739 or structural_blank != 1:
        raise ValueError(
            "Unexpected menu completion state: "
            f"translated={translated} blank={structural_blank}"
        )
    return rows


def load_move_rows() -> list[dict[str, str]]:
    rows = read_tsv(EXTRACTED / "moves.tsv")
    validate_unique_ids(rows, "moves.tsv")
    if len(rows) != 94:
        raise ValueError(f"Unexpected move row count: {len(rows)}")
    for row in rows:
        target = row["translation_zh"]
        if not target:
            raise ValueError(f"Untranslated move row: {row['id']}")
        validate_format_tokens(
            row["source_en"], target, row["id"], tags=True
        )
    return rows


def load_dialogue_plan() -> tuple[
    list[dict[str, str]],
    dict[str, dict[str, str]],
    dict[str, dict[str, str]],
]:
    source_rows = read_tsv(EXTRACTED / "dialogue.tsv")
    occurrence_rows = read_tsv(
        DEDUPLICATED / "dialogue_occurrences.tsv"
    )
    unique_rows = read_tsv(DEDUPLICATED / "dialogue_unique.tsv")
    validate_unique_ids(source_rows, "dialogue.tsv")
    validate_unique_ids(occurrence_rows, "dialogue_occurrences.tsv")
    unique_by_id = {row["unit_id"]: row for row in unique_rows}
    if len(unique_by_id) != len(unique_rows):
        raise ValueError("dialogue_unique.tsv contains duplicate unit IDs")
    source_by_id = {row["id"]: row for row in source_rows}
    occurrence_by_id = {row["id"]: row for row in occurrence_rows}
    if set(source_by_id) != set(occurrence_by_id):
        raise ValueError("Dialogue occurrence IDs do not reproduce source IDs")
    missing_units = sorted(
        {row["unit_id"] for row in occurrence_rows} - set(unique_by_id)
    )
    if missing_units:
        raise ValueError(
            f"Dialogue occurrences reference missing units: {missing_units[:5]}"
        )
    return occurrence_rows, source_by_id, unique_by_id


def choose_dialogue_text(
    occurrence: dict[str, str],
    source_by_id: dict[str, dict[str, str]],
    unique_by_id: dict[str, dict[str, str]],
) -> tuple[str, str]:
    source = source_by_id[occurrence["id"]]
    unit = unique_by_id[occurrence["unit_id"]]
    status = unit["status"]
    translation = unit["translation_zh"]
    if status == "translated":
        if not translation:
            raise ValueError(
                f"Translated dialogue unit is empty: {unit['unit_id']}"
            )
        validate_format_tokens(
            source["source_en"] or source["source_ru"],
            translation,
            occurrence["id"],
            tags=True,
        )
        return translation, "translated"
    if status == "blank":
        return "", "blank"
    # Pending and conflicting duplicate translations stay readable without
    # leaking CP1251 bytes into the custom high-byte carrier.  Shared files use
    # their aligned English display; the eight RU-only rows temporarily keep
    # Unicode Russian rendered through the same atlas.
    return source["source_en"] or source["source_ru"], "fallback"


def ordered_character_map(texts: list[str]) -> dict[str, int]:
    characters = sorted(
        {
            character
            for text in texts
            for character in text
            if ord(character) >= 0x80
        },
        key=ord,
    )
    if len(characters) > CARRIER_CAPACITY:
        raise ValueError(
            f"Build needs {len(characters)} non-ASCII glyphs; custom carrier "
            f"capacity is {CARRIER_CAPACITY}"
        )
    return {character: index for index, character in enumerate(characters)}


def carrier_pair(index: int) -> tuple[int, int]:
    if not 0 <= index < CARRIER_CAPACITY:
        raise ValueError(f"Carrier index out of range: {index}")
    return (
        LEAD_MIN + index // TAIL_COUNT,
        TAIL_MIN + index % TAIL_COUNT,
    )


def encode_text(text: str, mapping: dict[str, int]) -> bytes:
    result = bytearray()
    for character in text:
        value = ord(character)
        if value < 0x80:
            result.append(value)
            continue
        if character not in mapping:
            raise ValueError(f"Character absent from build map: {character!r}")
        result.extend(carrier_pair(mapping[character]))
    return bytes(result)


def build_msglist(
    source: bytes,
    rows: list[dict[str, str]],
    mapping: dict[str, int],
) -> bytes:
    translations = {
        row["key"]: row["translation_zh"]
        for row in rows
        if row["file"] == "MSGLIST.TXT"
    }
    appended = {
        row["key"]: row["translation_zh"]
        for row in rows
        if row["file"] == "rayne2.exe"
    }
    lines = source.splitlines(keepends=True)
    set_header(lines, b"Double byte support", b'"1"')
    set_header(lines, b"Double byte font", b'"' + FONT_FACE + b'"')
    prepared = b"".join(lines)
    seen: set[str] = set()

    def replace_pair(match: re.Match[bytes]) -> bytes:
        key_bytes = match.group(1)
        key = key_bytes.decode("ascii", errors="strict")
        if key not in translations:
            raise ValueError(f"Menu source key is absent from TSV: {key!r}")
        seen.add(key)
        value = translations[key]
        if not value and key:
            value = key
        return b'"' + key_bytes + b'", "' + encode_text(value, mapping) + b'"'

    result = PAIR_RE.sub(replace_pair, prepared)
    if seen != set(translations):
        missing = sorted(set(translations) - seen)
        raise ValueError(f"Menu TSV keys absent from source: {missing[:5]}")
    for key, value in appended.items():
        key_bytes = key.encode("ascii")
        result += (
            b'"'
            + key_bytes
            + b'", "'
            + encode_text(value, mapping)
            + b'"\r\n'
        )
    return result


def build_movelist(
    source: bytes,
    rows: list[dict[str, str]],
    mapping: dict[str, int],
) -> bytes:
    by_line = {int(row["line"]): row for row in rows}
    result: list[bytes] = []
    replaced: set[int] = set()
    for line_number, line in enumerate(
        source.splitlines(keepends=True), start=1
    ):
        row = by_line.get(line_number)
        if row is None:
            result.append(line)
            continue
        _, newline = split_newline(line)
        result.append(encode_text(row["translation_zh"], mapping) + newline)
        replaced.add(line_number)
    if replaced != set(by_line):
        missing = sorted(set(by_line) - replaced)
        raise ValueError(f"Move-list source lines are missing: {missing}")
    return b"".join(result)


def normalize_dialogue_key(key: str) -> str:
    match = re.search(r"[A-Za-z0-9_$@].*", key)
    return match.group(0) if match else key


def build_dialogue_entries(
    pod: Pod3,
    occurrences: list[dict[str, str]],
    source_by_id: dict[str, dict[str, str]],
    unique_by_id: dict[str, dict[str, str]],
    mapping: dict[str, int],
) -> tuple[dict[str, bytes], Counter[str]]:
    by_file: dict[str, dict[int, dict[str, str]]] = defaultdict(dict)
    for occurrence in occurrences:
        line_number = int(occurrence["line"])
        if line_number in by_file[occurrence["file"]]:
            raise ValueError(
                "Duplicate dialogue file/line occurrence: "
                f"{occurrence['file']}:{line_number}"
            )
        by_file[occurrence["file"]][line_number] = occurrence

    replacements: dict[str, bytes] = {}
    modes: Counter[str] = Counter()
    replaced_ids: set[str] = set()
    for filename, rows_by_line in sorted(by_file.items()):
        name = rf"WORLD\RU\{filename}"
        source = pod.read_entry(name)
        output: list[bytes] = []
        for line_number, line in enumerate(
            source.splitlines(keepends=True), start=1
        ):
            occurrence = rows_by_line.get(line_number)
            if occurrence is None:
                output.append(line)
                continue
            body, newline = split_newline(line)
            columns = body.split(b",", 2)
            if len(columns) != 3:
                raise ValueError(
                    f"Mapped dialogue line is not three-column: "
                    f"{filename}:{line_number}"
                )
            raw_key = columns[0].decode("cp1251")
            key = normalize_dialogue_key(raw_key.strip())
            expected_key = source_by_id[occurrence["id"]]["key"]
            if key.casefold() != expected_key.casefold():
                raise ValueError(
                    f"Dialogue key mismatch at {filename}:{line_number}: "
                    f"{key!r} != {expected_key!r}"
                )
            text, mode = choose_dialogue_text(
                occurrence, source_by_id, unique_by_id
            )
            output.append(
                columns[0]
                + b","
                + columns[1]
                + b","
                + encode_text(text, mapping)
                + newline
            )
            modes[mode] += 1
            replaced_ids.add(occurrence["id"])
        replacements[name] = b"".join(output)
    if replaced_ids != {row["id"] for row in occurrences}:
        missing = sorted(
            {row["id"] for row in occurrences} - replaced_ids
        )
        raise ValueError(f"Dialogue occurrences were not rebuilt: {missing[:5]}")
    return replacements, modes


def build_font_texture(
    mapping: dict[str, int],
) -> tuple[bytes, Image.Image]:
    source_header, source_image = read_tex(SOURCE_TEX)
    if source_image.size != (512, ATLAS_BASE_Y):
        raise ValueError(
            f"Unexpected source font texture size: {source_image.size}"
        )
    header = bytearray(source_header)
    struct.pack_into("<II", header, 8, ATLAS_WIDTH, ATLAS_HEIGHT)
    image = Image.new(
        "RGBA", (ATLAS_WIDTH, ATLAS_HEIGHT), (255, 255, 255, 0)
    )
    image.alpha_composite(source_image, (0, 0))
    font = ImageFont.truetype(str(CHINESE_FONT), FONT_SIZE)
    font.set_variation_by_axes([FONT_WEIGHT])
    draw = ImageDraw.Draw(image)
    for character, index in mapping.items():
        column = index % ATLAS_COLUMNS
        row = index // ATLAS_COLUMNS
        x = column * CELL_WIDTH
        y = ATLAS_BASE_Y + row * ROW_PITCH
        if y + GLYPH_HEIGHT > ATLAS_HEIGHT:
            raise ValueError("Chinese glyph atlas exceeded fixed dimensions")
        left, top, right, bottom = draw.textbbox(
            (0, 0), character, font=font
        )
        width = right - left
        height = bottom - top
        draw_x = x + (GLYPH_WIDTH - width) // 2 - left
        draw_y = y + (GLYPH_HEIGHT - height) // 2 - top
        draw.text(
            (draw_x, draw_y),
            character,
            font=font,
            fill=(255, 255, 255, 255),
        )
    return bytes(header), image


def build_font_definition() -> bytes:
    preamble: list[bytes] = []
    source_lines: dict[int, bytes] = {}
    for line in SOURCE_FNT.read_bytes().splitlines():
        if len(line) >= 2 and line[1:2] == b":":
            source_lines[line[0]] = line
        else:
            preamble.append(line)
    for value in range(LEAD_MIN, LEAD_MAX + 1):
        source_lines.pop(value, None)
    for value in range(TAIL_MIN, TAIL_MAX + 1):
        source_lines[value] = (
            bytes((value,))
            + f": 0,{ATLAS_HEIGHT - GLYPH_HEIGHT},"
            f"{GLYPH_WIDTH},{GLYPH_HEIGHT},0".encode("ascii")
        )
    result = [line + b"\r\n" for line in preamble]
    for value in sorted(source_lines):
        result.append(source_lines[value] + b"\r\n")
    return b"".join(result)


def write_character_map(mapping: dict[str, int]) -> Path:
    path = BUILD / "character_map.tsv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["character", "unicode", "carrier", "atlas_index"],
            dialect="excel-tab",
            lineterminator="\r\n",
        )
        writer.writeheader()
        for character, index in mapping.items():
            lead, tail = carrier_pair(index)
            writer.writerow(
                {
                    "character": character,
                    "unicode": f"U+{ord(character):04X}",
                    "carrier": f"{lead:02X}{tail:02X}",
                    "atlas_index": index,
                }
            )
    return path


def main() -> None:
    if sha256_file(BASELINE_LANGUAGE) != EXPECTED_LANGUAGE_SHA256:
        raise ValueError("LANGUAGE.POD baseline hash mismatch")
    if sha256_file(BASELINE_COMMON) != EXPECTED_COMMON_SHA256:
        raise ValueError("COMMON.POD baseline hash mismatch")
    if sha256_file(SOURCE_TEX) != EXPECTED_SOURCE_TEX_SHA256:
        raise ValueError("GOTHICTITLE_RU.TEX source hash mismatch")
    if sha256_file(SOURCE_FNT) != EXPECTED_SOURCE_FNT_SHA256:
        raise ValueError("GOTHICTITLE_RU.FNT source hash mismatch")
    if not CHINESE_FONT.exists():
        raise FileNotFoundError(f"Chinese font not found: {CHINESE_FONT}")

    pod = Pod3.read(BASELINE_LANGUAGE)
    common = Pod3.read(BASELINE_COMMON)
    if pod.verify_crcs():
        raise ValueError("Baseline LANGUAGE.POD has CRC failures")
    english_credits = common.read_entry(SOURCE_CREDITS_NAME)
    if (
        hashlib.sha256(english_credits).hexdigest().upper()
        != EXPECTED_SOURCE_CREDITS_SHA256
    ):
        raise ValueError("English credits source hash mismatch")
    english_credits.decode("ascii", errors="strict")

    menu_rows = load_menu_rows()
    move_rows = load_move_rows()
    occurrences, source_by_id, unique_by_id = load_dialogue_plan()
    dialogue_choices = [
        choose_dialogue_text(
            occurrence, source_by_id, unique_by_id
        )[0]
        for occurrence in occurrences
    ]
    texts = [
        row["translation_zh"] for row in menu_rows if row["translation_zh"]
    ]
    texts.extend(row["translation_zh"] for row in move_rows)
    texts.extend(dialogue_choices)
    mapping = ordered_character_map(texts)

    replacements = {
        MSGLIST_NAME: build_msglist(
            pod.read_entry(MSGLIST_NAME), menu_rows, mapping
        ),
        MOVELIST_NAME: build_movelist(
            pod.read_entry(MOVELIST_NAME), move_rows, mapping
        ),
        TARGET_CREDITS_NAME: english_credits,
    }
    dialogue_replacements, dialogue_modes = build_dialogue_entries(
        pod,
        occurrences,
        source_by_id,
        unique_by_id,
        mapping,
    )
    replacements.update(dialogue_replacements)
    effective_replacements = {
        name: blob
        for name, blob in replacements.items()
        if blob != pod.read_entry(name)
    }

    header, image = build_font_texture(mapping)
    tex_path = BUILD / "assets" / Path(TARGET_TEX_NAME.replace("\\", "/"))
    fnt_path = BUILD / "assets" / Path(TARGET_FNT_NAME.replace("\\", "/"))
    tex_path.parent.mkdir(parents=True, exist_ok=True)
    fnt_path.parent.mkdir(parents=True, exist_ok=True)
    write_tex(tex_path, header, image)
    fnt_path.write_bytes(build_font_definition())
    character_map_path = write_character_map(mapping)

    language_path = BUILD / "LANGUAGE.POD"
    language_path.parent.mkdir(parents=True, exist_ok=True)
    language_path.write_bytes(
        rebuild_entries(
            pod.data,
            effective_replacements,
            {
                TARGET_TEX_NAME: tex_path.read_bytes(),
                TARGET_FNT_NAME: fnt_path.read_bytes(),
            },
        )
    )
    built = Pod3.read(language_path)
    failures = built.verify_crcs()
    if failures:
        raise ValueError(f"Built LANGUAGE.POD CRC failures: {failures[:5]}")

    manifest = {
        "build_id": BUILD_ID,
        "proxy_sha256": sha256_file(PROJECT / "build" / "proxy" / "dinput8.dll"),
        "exe_sha256": "EAE3925A344668500F3533EBEC146376C8B1BBDB168ED2C3B1D4DECB0ABF0952",
        "translation_inputs": {
            str(path.relative_to(TRANSLATION)): sha256_file(path)
            for path in [EXTRACTED / "menu.tsv", EXTRACTED / "moves.tsv",
                         DEDUPLICATED / "dialogue_unique.tsv",
                         DEDUPLICATED / "dialogue_occurrences.tsv"]
        },
        "archive": {
            "filename": "LANGUAGE.POD",
            "base_sha256": EXPECTED_LANGUAGE_SHA256,
            "deployment_mode": "self-contained-rebuild",
            "font_entries_embedded": True,
            "requires_language_first_mount_patch": True,
            "requires_dynamic_glyph_patch": True,
        },
        "font": {
            "face": FONT_FACE.decode("ascii"),
            "source": "Source Han Sans SC / Noto Sans SC",
            "weight": FONT_WEIGHT,
            "size": FONT_SIZE,
            "stroke_width": 0,
            "atlas_width": ATLAS_WIDTH,
            "atlas_height": ATLAS_HEIGHT,
            "atlas_base_y": ATLAS_BASE_Y,
            "cell_width": CELL_WIDTH,
            "row_pitch": ROW_PITCH,
            "glyph_width": GLYPH_WIDTH,
            "glyph_height": GLYPH_HEIGHT,
        },
        "carrier": {
            "lead_range": f"{LEAD_MIN:02X}-{LEAD_MAX:02X}",
            "tail_range": f"{TAIL_MIN:02X}-{TAIL_MAX:02X}",
            "capacity": CARRIER_CAPACITY,
            "glyphs_used": len(mapping),
            "maximum_distinct_glyphs_per_draw": TAIL_COUNT,
        },
        "translations": {
            "menu_rows": len(menu_rows),
            "menu_translated": sum(
                bool(row["translation_zh"]) for row in menu_rows
            ),
            "menu_structural_blank": sum(
                not row["translation_zh"] for row in menu_rows
            ),
            "move_rows": len(move_rows),
            "dialogue_occurrences": len(occurrences),
            "dialogue_unique_units": len(unique_by_id),
            "dialogue_modes": dict(sorted(dialogue_modes.items())),
            "credits": "English Terminal Cut fallback",
        },
        "changed_existing_entries": sorted(effective_replacements),
        "targets": {
            TARGET_TEX_NAME: {
                "path": str(tex_path.relative_to(BUILD)),
                "sha256": sha256_file(tex_path),
                "embedded_in": "LANGUAGE.POD",
            },
            TARGET_FNT_NAME: {
                "path": str(fnt_path.relative_to(BUILD)),
                "sha256": sha256_file(fnt_path),
                "embedded_in": "LANGUAGE.POD",
            },
        },
        "character_map": {
            "path": str(character_map_path.relative_to(BUILD)),
            "sha256": sha256_file(character_map_path),
        },
        "language_sha256": sha256_file(language_path),
        "language_entry_count": built.entry_count,
    }
    (BUILD / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Built {BUILD_ID}")
    print(f"Menu: {len(menu_rows)} rows")
    print(f"Moves: {len(move_rows)} rows")
    print(
        "Dialogue occurrences: "
        f"{len(occurrences)} | modes={dict(dialogue_modes)}"
    )
    print(
        f"Dynamic glyphs: {len(mapping)} / {CARRIER_CAPACITY} "
        f"(per draw: {TAIL_COUNT})"
    )
    print(f"LANGUAGE.POD entries: {built.entry_count}")
    print(f"LANGUAGE.POD SHA-256: {sha256_file(language_path)}")


if __name__ == "__main__":
    main()
