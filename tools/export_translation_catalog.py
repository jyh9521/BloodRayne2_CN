from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict, deque
from dataclasses import asdict, dataclass
from pathlib import Path

from pod3 import Pod3, sha256_file


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "_cn_project"
BASELINE = PROJECT / "baseline" / "LANGUAGE.POD"
COMMON = ROOT / "COMMON.POD"
OUTPUT_DIR = PROJECT / "translation"
SPLIT_DIR = OUTPUT_DIR / "extracted"
CATALOG_PATH = OUTPUT_DIR / "catalog.tsv"
SUMMARY_PATH = OUTPUT_DIR / "inventory.json"
EXISTING_MENU_TRANSLATIONS = OUTPUT_DIR / "menu_ui_zh.tsv"

EXPECTED_SHA256 = (
    "2E3E0797E147E58B7308D3FCEDBDF0A06CB433FB099FC24B8FB38943D8B358E4"
)
EXPECTED_COMMON_SHA256 = (
    "1CC9A191D478AE87F97B454FD1D0419CE06A31709F8CB5B9D011D75EF83E3F18"
)
SPLIT_FILENAMES = {
    "dialogue": "dialogue.tsv",
    "menu": "menu.tsv",
    "moves": "moves.tsv",
    "credits": "credits.tsv",
}
HARDCODED_MENU_KEYS = {
    "FMV Presentation": "display option embedded in rayne2.exe",
    "Widescreen": "FMV presentation value embedded in rayne2.exe",
    "Original": "FMV presentation value embedded in rayne2.exe",
}
HARDCODED_MENU_TRANSLATIONS = {
    "FMV Presentation": "过场动画显示",
    "Widescreen": "宽屏",
    "Original": "原始比例",
}
PAIR_RE = re.compile(rb'"((?:[^"\\]|\\.)*)", "((?:[^"\\]|\\.)*)"')
TAG_RE = re.compile(r"@@[^@]+@@")


@dataclass
class CatalogRow:
    id: str
    kind: str
    file: str
    line: int
    key: str
    source_en: str
    source_ru: str
    translation_zh: str = ""
    status: str = "pending"
    notes: str = ""


def decode_entry(data: bytes, encoding: str) -> str:
    return data.decode(encoding).replace("\r\n", "\n").replace("\r", "\n")


def parse_three_column_lines(
    text: str, *, include_empty_display: bool = False
) -> list[tuple[int, str, str, str]]:
    rows: list[tuple[int, str, str, str]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        columns = line.split(",", 2)
        if len(columns) != 3:
            continue
        if not include_empty_display and not columns[2].strip():
            continue
        rows.append(
            (
                line_number,
                columns[0].strip(),
                columns[1],
                columns[2].strip(),
            )
        )
    return rows


def english_rows_by_key(
    pod: Pod3, entry_name: str
) -> dict[str, deque[tuple[str, str]]]:
    if entry_name not in pod.by_name:
        return {}
    text = decode_entry(pod.read_entry(entry_name), "cp1252")
    result: dict[str, deque[tuple[str, str]]] = defaultdict(deque)
    for _, key, speaker, display in parse_three_column_lines(
        text, include_empty_display=True
    ):
        result[key.casefold()].append((speaker, display))
    return result


def normalize_lookup_key(key: str) -> str:
    """Strip known non-ASCII garbage before otherwise ASCII resource keys."""
    match = re.search(r"[A-Za-z0-9_$@].*", key)
    return match.group(0) if match else key


def export_dialogue_rows(
    pod: Pod3, ru_names: list[str], rows: list[CatalogRow]
) -> dict[str, int]:
    stats = Counter()
    for ru_name in ru_names:
        filename = ru_name.rsplit("\\", 1)[-1]
        en_name = rf"WORLD\EN\{filename}"
        english = english_rows_by_key(pod, en_name)
        ru_text = decode_entry(pod.read_entry(ru_name), "cp1251")
        for line_number, key, ru_speaker, source_ru in parse_three_column_lines(
            ru_text
        ):
            source_en = ""
            status = "pending"
            note_parts: list[str] = []
            lookup_key = normalize_lookup_key(key)
            if lookup_key != key:
                note_parts.append(
                    f"stripped corrupt key prefix: {key[: -len(lookup_key)]!r}"
                )
            candidates = english.get(lookup_key.casefold())
            if candidates:
                en_speaker, source_en = candidates.popleft()
                if en_speaker.strip() != ru_speaker.strip():
                    note_parts.append(
                        f"speaker/control differs: EN={en_speaker.strip()!r}; "
                        f"RU={ru_speaker.strip()!r}"
                    )
                if not source_en:
                    status = "blank"
                    note_parts.append(
                        "English display is empty; clear RU-only speaker prefix"
                    )
                stats["matched_english"] += 1
            else:
                note_parts.append(
                    "no matching English row; translate from Russian"
                )
                stats["missing_english"] += 1
            row_id = f"dialogue:{filename}:{line_number}:{lookup_key}"
            rows.append(
                CatalogRow(
                    id=row_id,
                    kind="dialogue",
                    file=filename,
                    line=line_number,
                    key=lookup_key,
                    source_en=source_en,
                    source_ru=source_ru,
                    status=status,
                    notes="; ".join(note_parts),
                )
            )
            stats["rows"] += 1
    return dict(stats)


def export_msglist_rows(pod: Pod3, rows: list[CatalogRow]) -> dict[str, int]:
    name = r"WORLD\RU\MSGLIST.TXT"
    source = pod.read_entry(name)
    pair_count = 0
    for pair_count, match in enumerate(PAIR_RE.finditer(source), start=1):
        key = match.group(1).decode("ascii")
        source_ru = match.group(2).decode("cp1251")
        rows.append(
            CatalogRow(
                id=f"menu:MSGLIST.TXT:{pair_count}:{key}",
                kind="menu",
                file="MSGLIST.TXT",
                line=pair_count,
                key=key,
                source_en=key,
                source_ru=source_ru,
            )
        )
    for key, note in HARDCODED_MENU_KEYS.items():
        rows.append(
            CatalogRow(
                id=f"menu:rayne2.exe:0:{key}",
                kind="menu",
                file="rayne2.exe",
                line=0,
                key=key,
                source_en=key,
                source_ru="",
                notes=note,
            )
        )
    return {
        "language_rows": pair_count,
        "hardcoded_rows": len(HARDCODED_MENU_KEYS),
        "rows": pair_count + len(HARDCODED_MENU_KEYS),
    }


def export_movelist_rows(
    pod: Pod3, common: Pod3, rows: list[CatalogRow]
) -> dict[str, int]:
    name = r"WORLD\RU\MOVELIST.TXT"
    text = decode_entry(pod.read_entry(name), "cp1251")
    english_lines = decode_entry(
        common.read_entry(r"DATA\MOVELIST.TXT"), "cp1252"
    ).splitlines()
    count = 0
    tag_mismatch_count = 0
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if (
            not stripped
            or stripped.startswith("//")
            or stripped in {"/c", "/b"}
        ):
            continue
        visible = TAG_RE.sub("", stripped)
        if not any(character.isalpha() for character in visible):
            continue
        count += 1
        source_en = (
            english_lines[line_number - 1].strip()
            if line_number <= len(english_lines)
            else ""
        )
        note_parts = ["preserve every @@...@@ control token"]
        if not source_en:
            note_parts.append("no same-line English source")
        elif sorted(TAG_RE.findall(source_en)) != sorted(
            TAG_RE.findall(stripped)
        ):
            tag_mismatch_count += 1
            note_parts.append(
                "EN/RU control-token counts differ; use English structure"
            )
        rows.append(
            CatalogRow(
                id=f"moves:MOVELIST.TXT:{line_number}",
                kind="moves",
                file="MOVELIST.TXT",
                line=line_number,
                key="",
                source_en=source_en,
                source_ru=stripped,
                notes="; ".join(note_parts),
            )
        )
    return {"rows": count, "en_ru_tag_mismatches": tag_mismatch_count}


def export_credit_rows(common: Pod3, rows: list[CatalogRow]) -> dict[str, int]:
    name = r"DATA\CREDITS.TXT"
    text = decode_entry(common.read_entry(name), "cp1252")
    count = 0
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue
        count += 1
        note = ""
        if stripped.startswith("/b"):
            note = "preserve leading /b formatting directive"
        rows.append(
            CatalogRow(
                id=f"credits:CREDITS.TXT:{line_number}",
                kind="credits",
                file="CREDITS.TXT",
                line=line_number,
                key="",
                source_en=stripped,
                source_ru="",
                notes=note,
            )
        )
    return {"rows": count}


def write_catalog(path: Path, rows: list[CatalogRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(CatalogRow.__dataclass_fields__)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=fieldnames,
            dialect="excel-tab",
            lineterminator="\r\n",
        )
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)


def apply_existing_menu_translations(rows: list[CatalogRow]) -> int:
    with EXISTING_MENU_TRANSLATIONS.open(
        "r", encoding="utf-8-sig", newline=""
    ) as stream:
        source_rows = list(csv.DictReader(stream, dialect="excel-tab"))
    translations = {
        row["key"]: row["translation_zh"] for row in source_rows
    }
    translations.update(HARDCODED_MENU_TRANSLATIONS)
    menu_by_key = {
        row.key: row for row in rows if row.kind == "menu"
    }
    missing = sorted(set(translations) - set(menu_by_key))
    if missing:
        raise ValueError(
            f"Existing menu translations are absent from catalog: {missing}"
        )
    for key, translation in translations.items():
        row = menu_by_key[key]
        row.translation_zh = translation
        row.status = "translated"
    return len(translations)


def main() -> None:
    actual_hash = sha256_file(BASELINE)
    if actual_hash != EXPECTED_SHA256:
        raise ValueError(
            f"LANGUAGE.POD baseline mismatch: {actual_hash}"
        )
    actual_common_hash = sha256_file(COMMON)
    if actual_common_hash != EXPECTED_COMMON_SHA256:
        raise ValueError(
            f"COMMON.POD baseline mismatch: {actual_common_hash}"
        )

    pod = Pod3.read(BASELINE)
    common = Pod3.read(COMMON)
    failures = pod.verify_crcs()
    if failures:
        raise ValueError(f"LANGUAGE.POD has {len(failures)} CRC failures")

    names_by_language: dict[str, list[str]] = defaultdict(list)
    for entry in pod.entries:
        parts = entry.name.split("\\")
        if len(parts) >= 3 and parts[0] == "WORLD":
            names_by_language[parts[1]].append(entry.name)

    ru_names = sorted(names_by_language["RU"])
    dialogue_names = [
        name
        for name in ru_names
        if name.rsplit("\\", 1)[-1]
        not in {"MSGLIST.TXT", "MOVELIST.TXT", "CREDITLIST.TXT"}
    ]
    en_filenames = {
        name.rsplit("\\", 1)[-1] for name in names_by_language["EN"]
    }
    ru_dialogue_filenames = {
        name.rsplit("\\", 1)[-1] for name in dialogue_names
    }

    rows: list[CatalogRow] = []
    section_stats = {
        "dialogue": export_dialogue_rows(pod, dialogue_names, rows),
        "menu": export_msglist_rows(pod, rows),
        "moves": export_movelist_rows(pod, common, rows),
        "credits": export_credit_rows(common, rows),
    }
    section_stats["menu"]["existing_translations"] = (
        apply_existing_menu_translations(rows)
    )

    duplicate_ids = [
        row_id
        for row_id, count in Counter(row.id for row in rows).items()
        if count > 1
    ]
    if duplicate_ids:
        raise ValueError(f"Duplicate catalog IDs: {duplicate_ids[:10]}")

    write_catalog(CATALOG_PATH, rows)
    split_paths: dict[str, str] = {}
    for kind, filename in SPLIT_FILENAMES.items():
        path = SPLIT_DIR / filename
        write_catalog(path, [row for row in rows if row.kind == kind])
        split_paths[kind] = str(path)

    summary = {
        "baseline": {
            "path": str(BASELINE),
            "sha256": actual_hash,
            "pod_entries": pod.entry_count,
            "crc_failures": len(failures),
        },
        "common": {
            "path": str(COMMON),
            "sha256": actual_common_hash,
            "credits_source": r"DATA\CREDITS.TXT",
            "moves_source": r"DATA\MOVELIST.TXT",
        },
        "language_entry_counts": {
            language: len(names)
            for language, names in sorted(names_by_language.items())
        },
        "catalog": {
            "path": str(CATALOG_PATH),
            "split_paths": split_paths,
            "total_rows": len(rows),
            "by_kind": dict(sorted(Counter(row.kind for row in rows).items())),
            "sections": section_stats,
        },
        "coverage": {
            "shared_en_ru_dialogue_files": len(
                en_filenames & ru_dialogue_filenames
            ),
            "en_only_files": sorted(en_filenames - ru_dialogue_filenames),
            "ru_only_special_files": sorted(
                {
                    name.rsplit("\\", 1)[-1] for name in ru_names
                }
                - en_filenames
            ),
        },
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Wrote {CATALOG_PATH}")
    print(f"Wrote {SUMMARY_PATH}")
    print(f"Catalog rows: {len(rows)}")
    for kind, count in sorted(Counter(row.kind for row in rows).items()):
        print(f"  {kind}: {count}")
    dialogue = section_stats["dialogue"]
    print(
        "Dialogue English matches: "
        f"{dialogue['matched_english']}/{dialogue['rows']}"
    )


if __name__ == "__main__":
    main()
