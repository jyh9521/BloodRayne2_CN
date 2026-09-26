from __future__ import annotations

import csv
import hashlib
import json
import re
import struct
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from build_dbcs_probe import (
    DIALOGUE_PROBE_GBK,
    MSGLIST_NAME,
    PAIR_RE,
    ascii_scrub,
    split_newline,
    set_header,
)
from pod3 import Pod3, add_entries, patch_entries_fixed_capacity, sha256_file
from tex_rgba import read_tex, write_tex


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "_cn_project"
BASELINE_LANGUAGE = PROJECT / "baseline" / "LANGUAGE.POD"
BASELINE_COMMON = ROOT / "COMMON.POD"
SOURCE_FONTS = PROJECT / "source" / "w32art_fonts"
BUILD = PROJECT / "build" / "menu_probe"
MENU_TRANSLATIONS = PROJECT / "translation" / "menu_ui_zh.tsv"
EXPECTED_LANGUAGE_SHA256 = (
    "2E3E0797E147E58B7308D3FCEDBDF0A06CB433FB099FC24B8FB38943D8B358E4"
)
EXPECTED_COMMON_SHA256 = (
    "1CC9A191D478AE87F97B454FD1D0419CE06A31709F8CB5B9D011D75EF83E3F18"
)
BUILD_ID = "menu-ui-v10-language-font-overlay"

SOURCE_TEX = SOURCE_FONTS / "ART" / "GOTHICTITLE_RU.TEX"
SOURCE_FNT = SOURCE_FONTS / "DATA" / "GOTHICTITLE_RU.FNT"
EXPECTED_SOURCE_TEX_SHA256 = (
    "D20F28E1BEEE40F849AE09A1B382F87C1CA60CEDB5FEBC6AFC4C11B4DE288D50"
)
EXPECTED_SOURCE_FNT_SHA256 = (
    "CA633E6E57EA2A39FBDAC1B8C7F6F430F09D003B44DA66BF4D648CC0156A1DE8"
)
TARGET_TEX_NAME = r"ART\GOTHICTITLE_RU.TEX"
TARGET_FNT_NAME = r"DATA\GOTHICTITLE_RU.FNT"
SOURCE_CREDITS_NAME = r"DATA\CREDITS.TXT"
TARGET_CREDITS_NAME = r"WORLD\RU\CREDITLIST.TXT"
EXPECTED_SOURCE_CREDITS_SHA256 = (
    "D8539B6D58F1B84FFAF325CB4610614EA7C0968CFA538DA17EC4C945CAD83079"
)

CHINESE_FONT = Path(r"C:\Windows\Fonts\NotoSansSC-VF.ttf")
FONT_FACE = b"Noto Sans SC"
FONT_WEIGHT = 400
FONT_SIZE = 30
LEAD_BYTE = 0x81
# These are the control actions, main/pause/save/load/extras screens, and all
# camera/audio/display/control option labels.  Verbose runtime prompts fall
# back to their English source keys so dynamic ASCII text remains readable.
# The clean baseline is hash-pinned, so source pair indexes are stable.
MENU_SCOPE_RANGES = ((20, 61), (228, 297), (324, 390))
FORCE_SELECTED_MENU_KEYS = {
    "Enter cheat code",
    "Enter Cheat Code",
}
BUILTIN_MENU_TRANSLATIONS = {
    "Enter cheat code": "输入秘籍代码",
}
APPENDED_MENU_TRANSLATIONS = {
    "FMV Presentation": "过场动画显示",
    "Widescreen": "宽屏",
    "Original": "原始比例",
}
EXPECTED_SOURCE_MENU_ENTRY_COUNT = 145
MENU_EXCLUDED_KEYS = {
    "Load Game - Select Storage Device",
    "Save Game - Select Storage Device",
    "Xbox hard disk",
    "Please insert a memory unit",
    "Memory unit not formatted",
    "Select a different memory unit",
    "(Unformatted)",
    " free",
    "Only one save configuration is allowed",
    "Controller Disconnected!",
    "Please reconnect the controller and press START to continue.",
    "Please insert a controller and press START to continue.",
    "Quit game and load another game?",
    "Are you sure you wish to overwrite this save game?",
    "Quit game and lose current progress?",
    "This save data is corrupt. Overwrite?",
    "Restart level and lose current progress?",
    "(full)",
    "Game Complete",
    "Your current progress has been saved successfully.",
    "Enter pause menu",
    "Error",
    "Save Game?",
    "Game Over",
    "Retry From Last Checkpoint",
    "No sound devices.",
}
FORCED_TOKENS = ("自定义",)
NON_ASCII_RUN_RE = re.compile(r"[^\x00-\x7F]+")
PLACEHOLDER_RE = re.compile(r"@@[^@]+@@|%(?:[-+0-9.]*[A-Za-z%])|\\n")
# Preserve every printable ASCII slot.  The game uses more hidden prefix and
# formatting bytes than the source text alone reveals, so no single-byte
# punctuation may be repurposed.  0x81 is also excluded: it is the DBCS lead
# byte emitted before every Chinese token and becomes a visible prefix if the
# FNT defines a glyph for it.
SLOTS = tuple(value for value in range(0x80, 0xFF) if value != LEAD_BYTE)
ATLAS_WIDTH = 2048
ATLAS_HEIGHT = 1024


def ordered_unique_runs(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        for run in NON_ASCII_RUN_RE.findall(value):
            if run in seen:
                continue
            seen.add(run)
            result.append(run)
    return result


def segment_run(run: str, tokens: set[str]) -> list[str] | None:
    paths: list[list[str] | None] = [None] * (len(run) + 1)
    paths[0] = []
    ordered = sorted(tokens, key=lambda value: (-len(value), value))
    for start in range(len(run)):
        if paths[start] is None:
            continue
        for token in ordered:
            if run.startswith(token, start):
                end = start + len(token)
                candidate = paths[start] + [token]
                current = paths[end]
                if current is None or len(candidate) < len(current):
                    paths[end] = candidate
    return paths[-1]


def prune_compound_tokens(
    runs: list[str], protected: tuple[str, ...] = ()
) -> list[str]:
    ordered = list(dict.fromkeys([*runs, *protected]))
    tokens = set(ordered)
    for token in sorted(tokens, key=lambda value: (-len(value), value)):
        if token in protected:
            continue
        alternatives = tokens - {token}
        if segment_run(token, alternatives) is not None:
            tokens.remove(token)
    return [run for run in ordered if run in tokens]


def make_mapping(values: list[str]) -> dict[str, int]:
    runs = ordered_unique_runs(values)
    tokens = prune_compound_tokens(runs, FORCED_TOKENS)
    if len(tokens) > len(SLOTS):
        raise ValueError(
            f"Menu build needs {len(tokens)} token glyphs; only "
            f"{len(SLOTS)} safe carrier slots are available"
        )
    return dict(zip(tokens, SLOTS[: len(tokens)], strict=True))


def load_menu_translations(source: bytes) -> tuple[dict[str, str], list[int]]:
    source_keys: list[str] = []
    for match in PAIR_RE.finditer(source):
        source_keys.append(match.group(1).decode("ascii", errors="strict"))
    source_index = {key: index for index, key in enumerate(source_keys, 1)}

    with MENU_TRANSLATIONS.open(
        "r", encoding="utf-8-sig", newline=""
    ) as stream:
        rows = list(csv.DictReader(stream, dialect="excel-tab"))
    if not rows or set(rows[0]) != {"key", "translation_zh"}:
        raise ValueError("Unexpected menu translation TSV columns")

    all_translations: dict[str, str] = {}
    for row in rows:
        key = row["key"]
        value = row["translation_zh"]
        if key in all_translations:
            raise ValueError(f"Duplicate menu translation key: {key!r}")
        if key not in source_index:
            raise ValueError(f"Menu translation key not found: {key!r}")
        source_placeholders = sorted(PLACEHOLDER_RE.findall(key))
        target_placeholders = sorted(PLACEHOLDER_RE.findall(value))
        if source_placeholders != target_placeholders:
            raise ValueError(
                f"Placeholder mismatch for {key!r}: "
                f"{source_placeholders!r} != {target_placeholders!r}"
            )
        all_translations[key] = value
    for key, value in BUILTIN_MENU_TRANSLATIONS.items():
        if key not in source_index:
            raise ValueError(f"Built-in menu translation key not found: {key!r}")
        all_translations[key] = value

    selected: dict[str, str] = {}
    selected_indexes: list[int] = []
    for index, key in enumerate(source_keys, 1):
        if (
            not any(start <= index <= end for start, end in MENU_SCOPE_RANGES)
            and key not in FORCE_SELECTED_MENU_KEYS
        ):
            continue
        if key in MENU_EXCLUDED_KEYS:
            continue
        if key not in all_translations:
            continue
        selected[key] = all_translations[key]
        selected_indexes.append(index)
    if len(selected) != EXPECTED_SOURCE_MENU_ENTRY_COUNT:
        raise ValueError(
            f"Unexpected translated menu scope size: {len(selected)} != "
            f"{EXPECTED_SOURCE_MENU_ENTRY_COUNT}"
        )
    selected.update(APPENDED_MENU_TRANSLATIONS)
    return selected, selected_indexes


def make_values(menu: dict[str, str]) -> list[str]:
    values = list(menu.values())
    for translations in DIALOGUE_PROBE_GBK.values():
        values.extend(translations.values())
    return values


def encode_carrier(text: str, mapping: dict[str, int]) -> bytes:
    result = bytearray()
    cursor = 0
    tokens = set(mapping)
    while cursor < len(text):
        if ord(text[cursor]) < 0x80:
            result.append(ord(text[cursor]))
            cursor += 1
            continue
        match = NON_ASCII_RUN_RE.match(text, cursor)
        if match is None:
            raise AssertionError("Failed to identify non-ASCII run")
        run = match.group(0)
        segments = segment_run(run, tokens)
        if segments is None:
            raise ValueError(f"Chinese run cannot be tokenized: {run!r}")
        for token in segments:
            result.extend((LEAD_BYTE, mapping[token]))
        cursor = match.end()
    return bytes(result)


def build_msglist(
    source: bytes,
    menu: dict[str, str],
    mapping: dict[str, int],
) -> bytes:
    lines = source.splitlines(keepends=True)
    set_header(lines, b"Double byte support", b'"1"')
    set_header(lines, b"Double byte font", b'"' + FONT_FACE + b'"')
    prepared = b"".join(lines)

    def replace_pair(match: re.Match[bytes]) -> bytes:
        key_bytes = match.group(1)
        try:
            key = key_bytes.decode("ascii")
        except UnicodeDecodeError:
            return match.group(0)
        value = menu.get(key)
        if value is None:
            # The English key is also the canonical source UI string.  Using
            # it as the fallback prevents unhandled Russian bytes from
            # colliding with the high-byte Chinese token slots.
            return b'"' + key_bytes + b'", "' + key_bytes + b'"'
        return (
            b'"'
            + key_bytes
            + b'", "'
            + encode_carrier(value, mapping)
            + b'"'
        )

    result = PAIR_RE.sub(replace_pair, prepared)
    source_keys = {match.group(1) for match in PAIR_RE.finditer(source)}
    for key, value in APPENDED_MENU_TRANSLATIONS.items():
        key_bytes = key.encode("ascii")
        if key_bytes in source_keys:
            raise ValueError(f"Appended menu key already exists: {key!r}")
        result += (
            b'"'
            + key_bytes
            + b'", "'
            + encode_carrier(value, mapping)
            + b'"\r\n'
        )
    return result


def build_carrier_dialogue(
    source: bytes,
    translations: dict[str, str],
    mapping: dict[str, int],
) -> bytes:
    pending = dict(translations)
    result: list[bytes] = []
    for line in ascii_scrub(source).splitlines(keepends=True):
        body, newline = split_newline(line)
        columns = body.split(b",", 2)
        if len(columns) != 3:
            result.append(line)
            continue
        key = columns[0].decode("ascii", errors="strict")
        if key not in pending:
            result.append(line)
            continue
        result.append(
            columns[0]
            + b","
            + columns[1]
            + b","
            + encode_carrier(pending.pop(key), mapping)
            + newline
        )
    if pending:
        raise ValueError(f"Dialogue keys were not found: {sorted(pending)}")
    return b"".join(result)


def build_font_texture(
    mapping: dict[str, int],
) -> tuple[bytes, Image.Image, dict[int, tuple[int, int, int, int]]]:
    source_header, source_image = read_tex(SOURCE_TEX)
    header = bytearray(source_header)
    struct.pack_into("<II", header, 8, ATLAS_WIDTH, ATLAS_HEIGHT)
    image = Image.new(
        "RGBA", (ATLAS_WIDTH, ATLAS_HEIGHT), (255, 255, 255, 0)
    )
    image.alpha_composite(source_image, (0, 0))

    font = ImageFont.truetype(str(CHINESE_FONT), FONT_SIZE)
    font.set_variation_by_axes([FONT_WEIGHT])
    draw = ImageDraw.Draw(image)
    cell_height = 37
    row_pitch = 39
    padding_x = 2
    positions: dict[int, tuple[int, int, int, int]] = {}
    measurements: list[
        tuple[int, str, int, int, int, int, int]
    ] = []
    for token, slot in mapping.items():
        left, top, right, bottom = draw.textbbox((0, 0), token, font=font)
        cell_width = right - left + padding_x * 2
        measurements.append(
            (cell_width, token, slot, left, top, right, bottom)
        )

    rows: list[int] = []
    placements: dict[int, tuple[int, int]] = {}
    atlas_y = source_image.height
    for cell_width, token, slot, left, top, right, bottom in sorted(
        measurements, reverse=True
    ):
        del token, left, top, right, bottom
        for row_index, used_width in enumerate(rows):
            if used_width + cell_width <= image.width:
                placements[slot] = (used_width, atlas_y + row_index * row_pitch)
                rows[row_index] += cell_width
                break
        else:
            row_index = len(rows)
            y = atlas_y + row_index * row_pitch
            if y + cell_height > image.height:
                raise ValueError("Chinese tokens exceed GOTHICTITLE_RU atlas")
            placements[slot] = (0, y)
            rows.append(cell_width)

    for cell_width, token, slot, left, top, right, bottom in measurements:
        x, y = placements[slot]
        glyph_width = right - left
        glyph_height = bottom - top
        draw_x = x + padding_x - left
        draw_y = y + (cell_height - glyph_height) // 2 - top
        draw.text(
            (draw_x, draw_y),
            token,
            font=font,
            fill=(255, 255, 255, 255),
        )
        positions[slot] = (x, y, cell_width, cell_height)
    return bytes(header), image, positions


def build_font_definition(
    mapping: dict[str, int],
    positions: dict[int, tuple[int, int, int, int]],
) -> bytes:
    del mapping
    preamble: list[bytes] = []
    source_lines: dict[int, bytes] = {}
    for line in SOURCE_FNT.read_bytes().splitlines(keepends=True):
        body = line.rstrip(b"\r\n")
        if len(body) >= 2 and body[1:2] == b":":
            source_lines[body[0]] = body
        else:
            preamble.append(body)

    result = [line + b"\r\n" for line in preamble]
    all_slots = sorted(set(source_lines) | set(positions))
    for slot in all_slots:
        if slot in positions:
            x, y, width, height = positions[slot]
            result.append(
                bytes((slot,))
                + f": {x},{y},{width},{height},0".encode("ascii")
                + b"\r\n"
            )
        else:
            result.append(source_lines[slot] + b"\r\n")
    return b"".join(result)


def main() -> None:
    if sha256_file(BASELINE_LANGUAGE) != EXPECTED_LANGUAGE_SHA256:
        raise ValueError("LANGUAGE.POD baseline hash mismatch")
    if sha256_file(BASELINE_COMMON) != EXPECTED_COMMON_SHA256:
        raise ValueError("COMMON.POD baseline hash mismatch")
    if not CHINESE_FONT.exists():
        raise FileNotFoundError(f"Chinese font not found: {CHINESE_FONT}")
    if sha256_file(SOURCE_TEX) != EXPECTED_SOURCE_TEX_SHA256:
        raise ValueError("GOTHICTITLE_RU.TEX source hash mismatch")
    if sha256_file(SOURCE_FNT) != EXPECTED_SOURCE_FNT_SHA256:
        raise ValueError("GOTHICTITLE_RU.FNT source hash mismatch")

    pod = Pod3.read(BASELINE_LANGUAGE)
    common = Pod3.read(BASELINE_COMMON)
    english_credits = common.read_entry(SOURCE_CREDITS_NAME)
    if (
        hashlib.sha256(english_credits).hexdigest().upper()
        != EXPECTED_SOURCE_CREDITS_SHA256
    ):
        raise ValueError("English credits source hash mismatch")
    english_credits.decode("ascii", errors="strict")
    menu, selected_indexes = load_menu_translations(
        pod.read_entry(MSGLIST_NAME)
    )
    mapping = make_mapping(make_values(menu))

    header, image, positions = build_font_texture(mapping)
    tex_path = BUILD / "assets" / Path(TARGET_TEX_NAME.replace("\\", "/"))
    fnt_path = BUILD / "assets" / Path(TARGET_FNT_NAME.replace("\\", "/"))
    write_tex(tex_path, header, image)
    fnt_path.parent.mkdir(parents=True, exist_ok=True)
    fnt_path.write_bytes(build_font_definition(mapping, positions))

    replacements = {
        MSGLIST_NAME: build_msglist(
            pod.read_entry(MSGLIST_NAME), menu, mapping
        ),
        TARGET_CREDITS_NAME: english_credits,
    }
    for name, translations in DIALOGUE_PROBE_GBK.items():
        replacements[name] = build_carrier_dialogue(
            pod.read_entry(name), translations, mapping
        )

    language_path = BUILD / "LANGUAGE.POD"
    language_path.parent.mkdir(parents=True, exist_ok=True)
    patched_language = patch_entries_fixed_capacity(pod.data, replacements)
    language_path.write_bytes(
        add_entries(
            patched_language,
            {
                TARGET_TEX_NAME: tex_path.read_bytes(),
                TARGET_FNT_NAME: fnt_path.read_bytes(),
            },
        )
    )

    preview = BUILD / "GOTHICTITLE_RU_preview.png"
    dark = Image.new("RGBA", image.size, (32, 32, 32, 255))
    dark.alpha_composite(image)
    dark.save(preview)

    manifest = {
        "build_id": BUILD_ID,
        "archive": {
            "filename": "LANGUAGE.POD",
            "base_sha256": EXPECTED_LANGUAGE_SHA256,
            "deployment_mode": "self-contained-rebuild",
            "font_entries_embedded": True,
            "requires_language_first_mount_patch": True,
        },
        "lead_byte": f"{LEAD_BYTE:02X}",
        "font_face": FONT_FACE.decode("ascii"),
        "font_source": "Source Han Sans SC / Noto Sans SC",
        "font_weight": FONT_WEIGHT,
        "font_size": FONT_SIZE,
        "font_stroke_width": 0,
        "menu_scope_ranges": [list(item) for item in MENU_SCOPE_RANGES],
        "menu_force_selected_keys": sorted(FORCE_SELECTED_MENU_KEYS),
        "menu_excluded_keys": sorted(MENU_EXCLUDED_KEYS),
        "menu_appended_keys": sorted(APPENDED_MENU_TRANSLATIONS),
        "untranslated_menu_fallback": "English source key",
        "preserved_ascii_printable": "0x21-0x7F",
        "menu_source_indexes": selected_indexes,
        "menu": [
            {"key": key, "translation_zh": value}
            for key, value in menu.items()
        ],
        "dialogue": DIALOGUE_PROBE_GBK,
        "credits": {
            "target": TARGET_CREDITS_NAME,
            "source_archive": "COMMON.POD",
            "source": SOURCE_CREDITS_NAME,
            "source_sha256": EXPECTED_SOURCE_CREDITS_SHA256,
            "mode": "clean current-version English fallback",
        },
        "token_mapping": {
            token: f"{slot:02X}" for token, slot in mapping.items()
        },
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
        "language_sha256": sha256_file(language_path),
        "language_entry_count": Pod3.read(language_path).entry_count,
    }
    (BUILD / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Built menu probe in {BUILD}")
    print(f"Translated menu entries: {len(menu)}")
    print(f"Chinese token glyphs: {len(mapping)} / {len(SLOTS)}")
    print(f"LANGUAGE.POD SHA-256: {sha256_file(language_path)}")
    print(f"LANGUAGE.POD entries: {Pod3.read(language_path).entry_count}")
    print(f"GOTHICTITLE_RU.TEX bytes: {tex_path.stat().st_size}")
    print(f"GOTHICTITLE_RU.FNT bytes: {fnt_path.stat().st_size}")


if __name__ == "__main__":
    main()
