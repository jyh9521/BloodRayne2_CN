from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import os
import struct
from pathlib import Path

from pod3 import Pod3File, crc32_mpeg2, sha256_file


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def entry_capacity(pod: Pod3File, offset: int) -> int:
    offsets = sorted({entry.offset for entry in pod.entries})
    index = bisect.bisect_right(offsets, offset)
    next_offset = offsets[index] if index < len(offsets) else pod.file_size
    capacity = next_offset - offset
    if capacity <= 0:
        raise ValueError(f"Invalid POD slot capacity at offset {offset}")
    return capacity


def align_up(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


def load_patch_manifest(
    manifest_path: Path, build_root: Path
) -> tuple[dict, list[tuple[str, Path, str]]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    targets: list[tuple[str, Path, str]] = []
    for name, details in manifest["targets"].items():
        replacement = build_root / details["path"]
        if not replacement.is_file():
            raise FileNotFoundError(f"Missing replacement: {replacement}")
        expected = details["sha256"].upper()
        actual = sha256_file(replacement)
        if actual != expected:
            raise ValueError(
                f"Replacement hash mismatch for {name}: "
                f"expected={expected} actual={actual}"
            )
        targets.append((name, replacement, expected))
    return manifest, targets


def build_plan(
    archive: Path, manifest_path: Path, build_root: Path
) -> tuple[dict, list[dict]]:
    manifest, targets = load_patch_manifest(manifest_path, build_root)
    expected_archive = manifest["archive"]["base_sha256"].upper()
    actual_archive = sha256_file(archive)
    if actual_archive != expected_archive:
        raise ValueError(
            "Archive baseline hash mismatch: "
            f"expected={expected_archive} actual={actual_archive}"
        )

    pod = Pod3File(archive)
    plan: list[dict] = []
    patch_mode = manifest["archive"].get("patch_mode", "fixed")
    if patch_mode not in {"fixed", "append"}:
        raise ValueError(f"Unsupported archive patch mode: {patch_mode}")
    append_offset = align_up(pod.file_size, 16)
    with archive.open("rb") as stream:
        for name, replacement, replacement_hash in targets:
            if name not in pod.by_name:
                raise KeyError(f"Archive entry not found: {name}")
            entry = pod.by_name[name]
            capacity = entry_capacity(pod, entry.offset)
            blob = replacement.read_bytes()
            if patch_mode == "fixed" and len(blob) > capacity:
                raise ValueError(
                    f"Replacement exceeds physical slot for {name}: "
                    f"{len(blob)} > {capacity}"
                )
            stream.seek(entry.record_offset)
            record = stream.read(20)
            if len(record) != 20:
                raise ValueError(f"Entry record is truncated: {name}")
            stream.seek(entry.offset)
            slot = stream.read(capacity)
            if len(slot) != capacity:
                raise ValueError(f"Entry slot is truncated: {name}")
            original_blob = slot[: entry.size]
            if crc32_mpeg2(original_blob) != entry.checksum:
                raise ValueError(f"Original CRC mismatch: {name}")
            replacement_offset = (
                append_offset if patch_mode == "append" else entry.offset
            )
            plan.append(
                {
                    "name": name,
                    "mode": patch_mode,
                    "index": entry.index,
                    "record_offset": entry.record_offset,
                    "data_offset": entry.offset,
                    "replacement_offset": replacement_offset,
                    "capacity": capacity,
                    "original_size": entry.size,
                    "original_crc": f"{entry.checksum:08X}",
                    "original_sha256": sha256_bytes(original_blob),
                    "record_hex": record.hex(),
                    "slot_sha256": sha256_bytes(slot),
                    "replacement_path": str(replacement),
                    "replacement_size": len(blob),
                    "replacement_crc": f"{crc32_mpeg2(blob):08X}",
                    "replacement_sha256": replacement_hash,
                }
            )
            if patch_mode == "append":
                append_offset = align_up(
                    replacement_offset + len(blob), 16
                )
    return manifest, plan


def print_plan(archive: Path, plan: list[dict]) -> None:
    print(f"Archive: {archive}")
    for item in plan:
        print(
            f"{item['name']}: mode={item['mode']} "
            f"original={item['original_size']} "
            f"replacement={item['replacement_size']} "
            f"offset={item['replacement_offset']} "
            f"capacity={item['capacity']}"
        )


def restore_from_backup(archive: Path, backup_root: Path) -> None:
    state_path = backup_root / "restore_manifest.json"
    if not state_path.is_file():
        raise FileNotFoundError(f"Restore manifest not found: {state_path}")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    with archive.open("r+b") as stream:
        for item in state["entries"]:
            mode = item.get("mode", "fixed")
            if mode == "fixed":
                slot_path = backup_root / item["backup_file"]
                slot = slot_path.read_bytes()
                if sha256_bytes(slot) != item["slot_sha256"]:
                    raise ValueError(
                        f"Backup slot hash mismatch: {slot_path}"
                    )
                if len(slot) != item["capacity"]:
                    raise ValueError(
                        f"Backup slot size mismatch: {slot_path}"
                    )
                stream.seek(item["data_offset"])
                stream.write(slot)
            elif mode != "append":
                raise ValueError(
                    f"Unsupported restore mode for {item['name']}: {mode}"
                )
            record = bytes.fromhex(item["record_hex"])
            if len(record) != 20:
                raise ValueError(f"Backup record size mismatch: {item['name']}")
            stream.seek(item["record_offset"])
            stream.write(record)
        if any(item.get("mode") == "append" for item in state["entries"]):
            stream.truncate(state["base_archive_size"])
        stream.flush()
        os.fsync(stream.fileno())
    actual = sha256_file(archive)
    expected = state["base_archive_sha256"]
    if actual != expected:
        raise ValueError(
            f"Restored archive hash mismatch: expected={expected} actual={actual}"
        )
    print(f"Restored {archive}")
    print(f"SHA-256: {actual}")


def install(
    archive: Path,
    manifest_path: Path,
    build_root: Path,
    backup_root: Path,
) -> None:
    manifest, plan = build_plan(archive, manifest_path, build_root)
    state_path = backup_root / "restore_manifest.json"
    if state_path.exists():
        raise FileExistsError(
            f"Backup already exists; restore first or choose another path: "
            f"{state_path}"
        )
    backup_root.mkdir(parents=True, exist_ok=True)

    state = {
        "archive": str(archive.resolve()),
        "base_archive_sha256": manifest["archive"]["base_sha256"].upper(),
        "base_archive_size": archive.stat().st_size,
        "patch_manifest": str(manifest_path.resolve()),
        "entries": [],
    }
    with archive.open("rb") as stream:
        for number, item in enumerate(plan):
            saved = dict(item)
            if item["mode"] == "fixed":
                stream.seek(item["data_offset"])
                slot = stream.read(item["capacity"])
                backup_name = f"slot_{number:02d}.bin"
                (backup_root / backup_name).write_bytes(slot)
                saved["backup_file"] = backup_name
            state["entries"].append(saved)
    state_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    try:
        with archive.open("r+b") as stream:
            for item in plan:
                replacement = Path(item["replacement_path"]).read_bytes()
                if item["mode"] == "fixed":
                    padding = item["capacity"] - len(replacement)
                    stream.seek(item["data_offset"])
                    stream.write(replacement)
                    if padding:
                        stream.write(b"\0" * padding)
                else:
                    current_size = stream.seek(0, os.SEEK_END)
                    if current_size > item["replacement_offset"]:
                        raise ValueError(
                            f"Append offset overlaps archive for {item['name']}"
                        )
                    if current_size < item["replacement_offset"]:
                        stream.write(
                            b"\0"
                            * (item["replacement_offset"] - current_size)
                        )
                    stream.write(replacement)
                stream.seek(item["record_offset"] + 4)
                stream.write(struct.pack("<I", len(replacement)))
                stream.seek(item["record_offset"] + 8)
                stream.write(
                    struct.pack("<I", item["replacement_offset"])
                )
                stream.seek(item["record_offset"] + 16)
                stream.write(
                    struct.pack("<I", int(item["replacement_crc"], 16))
                )
            stream.flush()
            os.fsync(stream.fileno())

        patched = Pod3File(archive)
        for item in plan:
            entry = patched.by_name[item["name"]]
            blob = patched.read_entry(item["name"])
            if entry.size != item["replacement_size"]:
                raise ValueError(f"Patched size mismatch: {item['name']}")
            if sha256_bytes(blob) != item["replacement_sha256"]:
                raise ValueError(f"Patched hash mismatch: {item['name']}")
            if crc32_mpeg2(blob) != entry.checksum:
                raise ValueError(f"Patched CRC mismatch: {item['name']}")
        state["patched_archive_sha256"] = sha256_file(archive)
        state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception:
        restore_from_backup(archive, backup_root)
        raise

    print_plan(archive, plan)
    print(f"Patched SHA-256: {state['patched_archive_sha256']}")
    print(f"Restore data: {backup_root}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Safely patch fixed physical slots in a POD3 archive"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan")
    plan_parser.add_argument("archive", type=Path)
    plan_parser.add_argument("manifest", type=Path)
    plan_parser.add_argument("build_root", type=Path)

    install_parser = subparsers.add_parser("install")
    install_parser.add_argument("archive", type=Path)
    install_parser.add_argument("manifest", type=Path)
    install_parser.add_argument("build_root", type=Path)
    install_parser.add_argument("backup_root", type=Path)

    restore_parser = subparsers.add_parser("restore")
    restore_parser.add_argument("archive", type=Path)
    restore_parser.add_argument("backup_root", type=Path)

    args = parser.parse_args()
    if args.command == "plan":
        _, plan = build_plan(args.archive, args.manifest, args.build_root)
        print_plan(args.archive, plan)
    elif args.command == "install":
        install(
            args.archive,
            args.manifest,
            args.build_root,
            args.backup_root,
        )
    else:
        restore_from_backup(args.archive, args.backup_root)


if __name__ == "__main__":
    main()
