from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from patch_pod_slots import install, restore_from_backup, sha256_bytes
from pod3 import Pod3File, sha256_file


ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "_cn_project" / "baseline" / "LANGUAGE.POD"
TARGET = r"WORLD\RU\0COMBAT.TXT"


def main() -> None:
    baseline_hash = sha256_file(BASELINE)
    with tempfile.TemporaryDirectory(prefix="br2_pod_patch_test_") as temp:
        root = Path(temp)
        archive = root / "LANGUAGE.POD"
        shutil.copyfile(BASELINE, archive)
        pod = Pod3File(archive)
        original = pod.read_entry(TARGET)
        if not original:
            raise ValueError("Test entry is empty")
        replacement = bytes((original[0] ^ 1,)) + original[1:]

        build = root / "build"
        asset = build / "replacement.bin"
        build.mkdir()
        asset.write_bytes(replacement)
        manifest = {
            "archive": {
                "filename": "LANGUAGE.POD",
                "base_sha256": baseline_hash,
            },
            "targets": {
                TARGET: {
                    "path": asset.name,
                    "sha256": sha256_bytes(replacement),
                }
            },
        }
        manifest_path = build / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        backup = root / "backup"

        install(archive, manifest_path, build, backup)
        if sha256_file(archive) == baseline_hash:
            raise AssertionError("Patch test did not change the archive")
        restore_from_backup(archive, backup)
        if sha256_file(archive) != baseline_hash:
            raise AssertionError("Patch test did not restore exact baseline")
    print("OK: install and byte-exact restore round trip")


if __name__ == "__main__":
    main()
