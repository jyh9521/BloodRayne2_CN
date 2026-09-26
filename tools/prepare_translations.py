from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "_cn_project"
EXTRACTED = PROJECT / "translation" / "extracted"
BACKUPS = PROJECT / "translation" / "backups"
DEDUPLICATED = PROJECT / "translation" / "dialogue_deduplicated"

MENU_PATH = EXTRACTED / "menu.tsv"
MOVES_PATH = EXTRACTED / "moves.tsv"
DIALOGUE_PATH = EXTRACTED / "dialogue.tsv"
CATALOG_PATH = PROJECT / "translation" / "catalog.tsv"
UNIQUE_PATH = DEDUPLICATED / "dialogue_unique.tsv"
OCCURRENCES_PATH = DEDUPLICATED / "dialogue_occurrences.tsv"
SUMMARY_PATH = DEDUPLICATED / "summary.json"

CATALOG_FIELDS = [
    "id",
    "kind",
    "file",
    "line",
    "key",
    "source_en",
    "source_ru",
    "translation_zh",
    "status",
    "notes",
]
UNIQUE_FIELDS = [
    "unit_id",
    "kind",
    "source_en",
    "source_ru",
    "translation_zh",
    "status",
    "occurrence_count",
    "file_count",
    "first_file",
    "first_line",
    "first_key",
    "notes",
]
OCCURRENCE_FIELDS = [
    "id",
    "unit_id",
    "file",
    "line",
    "key",
    "source_status",
    "original_translation_zh",
    "notes",
]

MENU_COMPLETIONS = {
    "Load failed! Check memory card (PS2) in %s and please try again.": (
        "载入失败！请检查 %s 中的存储卡（PS2），然后重试。"
    ),
    "Save failed! Check memory card (PS2) in %s and please try again": (
        "保存失败！请检查 %s 中的存储卡（PS2），然后重试。"
    ),
    "acquired": "已获得",
    "acquired2": "已获得",
}

TAG_RE = re.compile(r"@@[^@]+@@")
FORMAT_RE = re.compile(
    r"%(?:\d+\$)?[-+#0 ]*(?:\d+|\*)?(?:\.\d+|\.\*)?"
    r"[hlLzjtI]*(?:[diuoxXfFeEgGaAcspn%])"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest().upper()


def read_tsv(
    path: Path, expected_fields: list[str], id_field: str = "id"
) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, dialect="excel-tab")
        if reader.fieldnames != expected_fields:
            raise ValueError(
                f"Unexpected columns in {path}: {reader.fieldnames}"
            )
        rows = list(reader)
    ids = [row[id_field] for row in rows]
    duplicate_ids = [
        row_id for row_id, count in Counter(ids).items() if count > 1
    ]
    if duplicate_ids:
        raise ValueError(f"Duplicate IDs in {path}: {duplicate_ids[:10]}")
    return rows


def write_tsv(
    path: Path, rows: list[dict[str, object]], fieldnames: list[str]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=fieldnames,
            dialect="excel-tab",
            lineterminator="\r\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def backup_once(path: Path) -> Path:
    digest = sha256_file(path)
    target = BACKUPS / f"{path.stem}.{digest[:12]}.tsv"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copy2(path, target)
    return target


def tokens(text: str) -> tuple[Counter[str], Counter[str]]:
    return Counter(TAG_RE.findall(text)), Counter(FORMAT_RE.findall(text))


def validate_tokens(
    source: str, translation: str, row_id: str
) -> list[str]:
    source_tags, source_formats = tokens(source)
    target_tags, target_formats = tokens(translation)
    failures: list[str] = []
    if source_tags != target_tags:
        failures.append(
            f"{row_id}: control tokens differ: "
            f"{dict(source_tags)} != {dict(target_tags)}"
        )
    if source_formats != target_formats:
        failures.append(
            f"{row_id}: format placeholders differ: "
            f"{dict(source_formats)} != {dict(target_formats)}"
        )
    return failures


def prepare_menu() -> tuple[list[dict[str, str]], dict[str, object]]:
    rows = read_tsv(MENU_PATH, CATALOG_FIELDS)
    before_hash = sha256_file(MENU_PATH)
    backup = backup_once(MENU_PATH)
    completed: list[str] = []
    structural_blank = 0
    failures: list[str] = []
    for row in rows:
        key = row["key"]
        if not row["translation_zh"].strip() and key in MENU_COMPLETIONS:
            row["translation_zh"] = MENU_COMPLETIONS[key]
            completed.append(key)
        if not key and not row["source_en"] and not row["source_ru"]:
            structural_blank += 1
            row["status"] = "blank"
            continue
        if not row["translation_zh"].strip():
            failures.append(f"{row['id']}: missing translation")
            continue
        row["status"] = "translated"
        failures.extend(
            validate_tokens(row["source_en"], row["translation_zh"], row["id"])
        )
    if failures:
        raise ValueError("Menu validation failed:\n" + "\n".join(failures))
    write_tsv(MENU_PATH, rows, CATALOG_FIELDS)
    return rows, {
        "rows": len(rows),
        "translated": sum(row["status"] == "translated" for row in rows),
        "structural_blank": structural_blank,
        "completed_keys": completed,
        "backup": str(backup),
        "sha256_before": before_hash,
        "sha256_after": sha256_file(MENU_PATH),
    }


def prepare_moves() -> tuple[list[dict[str, str]], dict[str, object]]:
    rows = read_tsv(MOVES_PATH, CATALOG_FIELDS)
    before_hash = sha256_file(MOVES_PATH)
    backup = backup_once(MOVES_PATH)
    failures: list[str] = []
    for row in rows:
        if not row["translation_zh"].strip():
            failures.append(f"{row['id']}: missing translation")
            continue
        row["status"] = "translated"
        # Four Russian rows abbreviate repeated buttons as "3 times".
        # The English source retains the complete runtime token sequence.
        failures.extend(
            validate_tokens(row["source_en"], row["translation_zh"], row["id"])
        )
    if failures:
        raise ValueError("Moves validation failed:\n" + "\n".join(failures))
    write_tsv(MOVES_PATH, rows, CATALOG_FIELDS)
    return rows, {
        "rows": len(rows),
        "translated": sum(row["status"] == "translated" for row in rows),
        "backup": str(backup),
        "sha256_before": before_hash,
        "sha256_after": sha256_file(MOVES_PATH),
    }


def dialogue_group_key(row: dict[str, str]) -> tuple[str, str]:
    return row["source_en"].strip(), row["source_ru"].strip()


def unit_id_for(key: tuple[str, str]) -> str:
    digest = hashlib.sha256(
        (key[0] + "\0" + key[1]).encode("utf-8")
    ).hexdigest()[:16]
    return f"dialogue-unit:{digest}"


def prepare_dialogue() -> tuple[list[dict[str, str]], dict[str, object]]:
    rows = read_tsv(DIALOGUE_PATH, CATALOG_FIELDS)
    existing_by_unit: dict[str, dict[str, str]] = {}
    if UNIQUE_PATH.exists():
        existing_rows = read_tsv(
            UNIQUE_PATH, UNIQUE_FIELDS, id_field="unit_id"
        )
        existing_by_unit = {
            row["unit_id"]: row for row in existing_rows
        }
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    ordered_keys: list[tuple[str, str]] = []
    for row in rows:
        key = dialogue_group_key(row)
        if key not in groups:
            ordered_keys.append(key)
        groups[key].append(row)

    unique_rows: list[dict[str, object]] = []
    occurrence_rows: list[dict[str, object]] = []
    conflict_groups = 0
    token_review_groups = 0
    translated_units = 0
    pending_units = 0
    blank_units = 0

    for key in ordered_keys:
        group = groups[key]
        unit_id = unit_id_for(key)
        existing = existing_by_unit.get(unit_id)
        candidate_order: list[str] = []
        candidate_counts: Counter[str] = Counter()
        existing_value = (
            existing["translation_zh"].strip() if existing else ""
        )
        existing_resolved = bool(
            existing
            and existing["status"] == "translated"
            and existing_value
        )
        if existing_value:
            candidate_order.append(existing_value)
            candidate_counts[existing_value] += 1
        if not existing_resolved:
            for row in group:
                value = row["translation_zh"].strip()
                if not value:
                    continue
                if value not in candidate_counts:
                    candidate_order.append(value)
                candidate_counts[value] += 1

        note_parts: list[str] = []
        translation = candidate_order[0] if candidate_order else ""
        if len(candidate_order) > 1:
            conflict_groups += 1
            note_parts.append(
                "needs review: "
                f"{len(candidate_order)} existing translation variants; "
                "the first occurrence is retained"
            )

        statuses = {row["status"] for row in group}
        if existing and existing["status"] == "blank":
            translation = ""
            status = "blank"
            blank_units += 1
        elif not translation and statuses == {"blank"}:
            status = "blank"
            blank_units += 1
        elif not translation:
            status = "pending"
            pending_units += 1
        else:
            status = "translated"
            source_for_tokens = key[0] or key[1]
            token_failures = validate_tokens(
                source_for_tokens, translation, unit_id
            )
            if token_failures:
                token_review_groups += 1
                status = "needs_review"
                note_parts.extend(token_failures)
            if len(candidate_order) > 1:
                status = "needs_review"
            if status == "translated":
                translated_units += 1

        if len(candidate_order) > 1:
            variant_summary = [
                {
                    "count": candidate_counts[value],
                    "translation": value,
                }
                for value in candidate_order
            ]
            note_parts.append(
                "variants=" + json.dumps(
                    variant_summary, ensure_ascii=False, separators=(",", ":")
                )
            )

        unique_rows.append(
            {
                "unit_id": unit_id,
                "kind": "dialogue",
                "source_en": key[0],
                "source_ru": key[1],
                "translation_zh": translation,
                "status": status,
                "occurrence_count": len(group),
                "file_count": len({row["file"] for row in group}),
                "first_file": group[0]["file"],
                "first_line": group[0]["line"],
                "first_key": group[0]["key"],
                "notes": "; ".join(note_parts),
            }
        )
        for row in group:
            occurrence_rows.append(
                {
                    "id": row["id"],
                    "unit_id": unit_id,
                    "file": row["file"],
                    "line": row["line"],
                    "key": row["key"],
                    "source_status": row["status"],
                    "original_translation_zh": row["translation_zh"],
                    "notes": row["notes"],
                }
            )

    occurrence_by_id = {row["id"]: row for row in occurrence_rows}
    occurrence_rows = [occurrence_by_id[row["id"]] for row in rows]
    if len(occurrence_rows) != len(rows):
        raise AssertionError("Dialogue occurrence mapping lost rows")
    if len({row["id"] for row in occurrence_rows}) != len(rows):
        raise AssertionError("Dialogue occurrence mapping has duplicate IDs")
    if sum(int(row["occurrence_count"]) for row in unique_rows) != len(rows):
        raise AssertionError("Dialogue occurrence counts do not reconcile")

    write_tsv(UNIQUE_PATH, unique_rows, UNIQUE_FIELDS)
    write_tsv(OCCURRENCES_PATH, occurrence_rows, OCCURRENCE_FIELDS)
    return rows, {
        "source_rows": len(rows),
        "source_files": len({row["file"] for row in rows}),
        "unique_units": len(unique_rows),
        "duplicate_rows_eliminated": len(rows) - len(unique_rows),
        "duplicate_groups": sum(
            int(row["occurrence_count"]) > 1 for row in unique_rows
        ),
        "translated_units": translated_units,
        "pending_units": pending_units,
        "blank_units": blank_units,
        "needs_review_units": sum(
            row["status"] == "needs_review" for row in unique_rows
        ),
        "translation_conflict_groups": conflict_groups,
        "token_review_groups": token_review_groups,
        "unique_path": str(UNIQUE_PATH),
        "occurrences_path": str(OCCURRENCES_PATH),
        "unique_sha256": sha256_file(UNIQUE_PATH),
        "occurrences_sha256": sha256_file(OCCURRENCES_PATH),
    }


def sync_catalog(
    menu_rows: list[dict[str, str]],
    moves_rows: list[dict[str, str]],
    dialogue_rows: list[dict[str, str]],
) -> dict[str, object]:
    rows = read_tsv(CATALOG_PATH, CATALOG_FIELDS)
    before_hash = sha256_file(CATALOG_PATH)
    backup = backup_once(CATALOG_PATH)
    by_id = {row["id"]: row for row in rows}
    source_rows = [*menu_rows, *moves_rows, *dialogue_rows]
    for source in source_rows:
        target = by_id.get(source["id"])
        if target is None:
            raise ValueError(f"Catalog row is missing: {source['id']}")
        for field in (
            "kind",
            "file",
            "line",
            "key",
            "source_en",
            "source_ru",
        ):
            if target[field] != source[field]:
                raise ValueError(
                    f"Catalog mismatch for {source['id']} field {field}"
                )
        target["translation_zh"] = source["translation_zh"]
        target["status"] = source["status"]
        target["notes"] = source["notes"]
    write_tsv(CATALOG_PATH, rows, CATALOG_FIELDS)
    return {
        "rows": len(rows),
        "synchronized_rows": len(source_rows),
        "credits_policy": "not translated; keep English fallback",
        "backup": str(backup),
        "sha256_before": before_hash,
        "sha256_after": sha256_file(CATALOG_PATH),
    }


def main() -> None:
    menu_rows, menu_summary = prepare_menu()
    moves_rows, moves_summary = prepare_moves()
    dialogue_rows, dialogue_summary = prepare_dialogue()
    catalog_summary = sync_catalog(
        menu_rows, moves_rows, dialogue_rows
    )
    summary = {
        "policy": {
            "menu": "translate and import",
            "moves": "translate and import",
            "dialogue": (
                "translate unique units; import each unit into every mapped "
                "shipped occurrence"
            ),
            "credits": "do not translate; keep current English fallback",
        },
        "menu": menu_summary,
        "moves": moves_summary,
        "dialogue": dialogue_summary,
        "catalog": catalog_summary,
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
