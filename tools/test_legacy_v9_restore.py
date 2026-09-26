from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "_cn_project"
CLEAN_ART_SHA256 = (
    "8B9A06FEEA6881026C485100BA24AADFD1C8ADA60400327C7E0F87098FF84631"
)
CLEAN_LANGUAGE_SHA256 = (
    "2E3E0797E147E58B7308D3FCEDBDF0A06CB433FB099FC24B8FB38943D8B358E4"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest().upper()


def copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def main() -> None:
    active_backup = PROJECT / "test_backup" / "menu_probe"
    if not (active_backup / "restore_manifest.json").is_file():
        raise FileNotFoundError("No active legacy v9 restore manifest")

    with tempfile.TemporaryDirectory(prefix="br2_cn_v9_restore_") as temporary:
        game = Path(temporary)
        fake_project = game / "_cn_project"
        fake_backup = fake_project / "test_backup" / "menu_probe"

        copy(ROOT / "W32ART.POD", game / "W32ART.POD")
        original_art_sha256 = sha256_file(game / "W32ART.POD")
        copy(ROOT / "LANGUAGE.POD", game / "LANGUAGE.POD")
        copy(ROOT / "dinput8.dll", game / "dinput8.dll")
        copy(
            PROJECT / "baseline" / "LANGUAGE.POD",
            fake_project / "baseline" / "LANGUAGE.POD",
        )
        copy(
            PROJECT / "tools" / "patch_pod_slots.py",
            fake_project / "tools" / "patch_pod_slots.py",
        )
        copy(
            PROJECT / "tools" / "pod3.py",
            fake_project / "tools" / "pod3.py",
        )
        copy(
            PROJECT / "test_package" / "restore_pure.ps1",
            fake_project / "test_package" / "restore_pure.ps1",
        )
        for filename in [
            "restore_manifest.json",
            "installed_proxy.sha256",
            "slot_00.bin",
            "slot_01.bin",
        ]:
            source = active_backup / filename
            if source.is_file():
                copy(source, fake_backup / filename)

        state = json.loads(
            (active_backup / "restore_manifest.json").read_text(encoding="utf-8-sig")
        )
        original_language_file = state.get("original_language_file")
        if original_language_file:
            source = active_backup / original_language_file
            if not source.is_file():
                raise FileNotFoundError(
                    f"Active original LANGUAGE.POD backup is missing: {source}"
                )
            copy(source, fake_backup / original_language_file)

        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(fake_project / "test_package" / "restore_pure.ps1"),
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if completed.returncode:
            raise RuntimeError(
                f"Legacy restore failed ({completed.returncode})\n"
                f"STDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
            )
        restored_art_sha256 = sha256_file(game / "W32ART.POD")
        if state.get("deployment_mode") == "language_self_contained":
            if restored_art_sha256 != original_art_sha256:
                raise AssertionError("Self-contained restore changed W32ART")
        elif restored_art_sha256 != CLEAN_ART_SHA256:
            raise AssertionError("Legacy restore did not recover clean W32ART")
        if sha256_file(game / "LANGUAGE.POD") != CLEAN_LANGUAGE_SHA256:
            raise AssertionError("Legacy restore did not recover clean LANGUAGE")
        if (game / "dinput8.dll").exists():
            raise AssertionError("Legacy restore left dinput8.dll in place")
        if (fake_backup / "restore_manifest.json").exists():
            raise AssertionError("Legacy restore left an active manifest")

        print("OK: installed " + str(state.get("package_build_id", "legacy v9")) + " restore on isolated copy")
        print(f"W32ART.POD:   {restored_art_sha256}")
        print(f"LANGUAGE.POD: {CLEAN_LANGUAGE_SHA256}")


if __name__ == "__main__":
    main()
