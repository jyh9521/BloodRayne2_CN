from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "_cn_project"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def run_script(path: Path) -> str:
    command = (["C:/Program Files/Git/bin/bash.exe", str(path)] if path.suffix==".sh" else [
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(path)])
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"{path.name} failed ({completed.returncode})\n"
            f"STDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
        )
    return completed.stdout


def main() -> None:
    with tempfile.TemporaryDirectory(
        prefix="br2_cn_language_deploy_"
    ) as temporary:
        game = Path(temporary)
        copy(ROOT / "rayne2.exe", game / "rayne2.exe")
        fake_project = game / "_cn_project"
        package = fake_project / "test_package"
        for filename in [
            "install_menu_probe.ps1",
            "restore_pure.ps1",
            "ROLLBACK.sh",
        ]:
            copy(
                PROJECT / "test_package" / filename,
                package / filename,
            )
        copy(
            PROJECT / "baseline" / "LANGUAGE.POD",
            fake_project / "baseline" / "LANGUAGE.POD",
        )
        copy(
            PROJECT / "build" / "full_translation" / "LANGUAGE.POD",
            fake_project / "build" / "full_translation" / "LANGUAGE.POD",
        )
        copy(
            PROJECT / "build" / "full_translation" / "manifest.json",
            fake_project / "build" / "full_translation" / "manifest.json",
        )
        copy(
            PROJECT / "build" / "proxy" / "dinput8.dll",
            fake_project / "build" / "proxy" / "dinput8.dll",
        )
        copy(
            fake_project / "baseline" / "LANGUAGE.POD",
            game / "LANGUAGE.POD",
        )
        copy(
            PROJECT / "translation" / "inventory.json",
            game / "W32ART.POD",
        )
        (game / "W32ENSND.POD").write_bytes(b"USER_ENGLISH_VOICE_MOD")
        sound_hash = sha256(game / "W32ENSND.POD")

        clean_language_hash = sha256(game / "LANGUAGE.POD")
        original_art_hash = sha256(game / "W32ART.POD")
        install_output = run_script(package / "install_menu_probe.ps1")
        if sha256(game / "W32ART.POD") != original_art_hash:
            raise AssertionError("Installer changed W32ART.POD")
        if sha256(game / "LANGUAGE.POD") != sha256(
            fake_project / "build" / "full_translation" / "LANGUAGE.POD"
        ):
            raise AssertionError("Installer did not deploy built LANGUAGE.POD")
        if sha256(game / "dinput8.dll") != sha256(
            fake_project / "build" / "proxy" / "dinput8.dll"
        ):
            raise AssertionError("Installer did not deploy proxy")
        if sha256(game / "W32ENSND.POD") != sound_hash:
            raise AssertionError("Installer changed sound mod")

        copy(
            PROJECT / "translation" / "menu_ui_zh.tsv",
            game / "W32ART.POD",
        )
        modded_art_hash = sha256(game / "W32ART.POD")
        (game / "W32ENSND.POD").write_bytes(b"REPLACED_ENGLISH_VOICE_MOD_AFTER_INSTALL")
        sound_hash = sha256(game / "W32ENSND.POD")
        restore_output = run_script(package / "ROLLBACK.sh")
        if sha256(game / "LANGUAGE.POD") != clean_language_hash:
            raise AssertionError("Restore did not recover original language")
        if sha256(game / "W32ART.POD") != modded_art_hash:
            raise AssertionError("Restore overwrote modded W32ART.POD")
        if (game / "dinput8.dll").exists():
            raise AssertionError("Restore left the proxy in the game root")
        if sha256(game / "W32ENSND.POD") != sound_hash:
            raise AssertionError("Restore changed replacement sound mod")
        if (
            fake_project
            / "test_backup"
            / "menu_probe"
            / "restore_manifest.json"
        ).exists():
            raise AssertionError("Restore left an active manifest")

        print("OK: self-contained install/restore round trip")
        print(f"Original W32ART marker: {original_art_hash}")
        print(f"Modded W32ART marker:   {modded_art_hash}")
        print("Installer reported untouched:", "untouched" in install_output)
        print("Restore reported state:", "LANGUAGE.POD" in restore_output)
        print("PASS: W32ENSND.POD mod unchanged by install/restore")

        # A mismatched package must fail before touching the installation.
        dll = fake_project / "build" / "proxy" / "dinput8.dll"
        pod = fake_project / "build" / "full_translation" / "LANGUAGE.POD"
        for candidate in [dll, pod, game / "rayne2.exe"]:
            saved = candidate.read_bytes()
            candidate.write_bytes(saved + b"TAMPER_TEST")
            try:
                run_script(package / "install_menu_probe.ps1")
            except RuntimeError:
                pass
            else:
                raise AssertionError("Mismatched input was accepted: " + candidate.name)
            finally:
                candidate.write_bytes(saved)
            assert sha256(game / "LANGUAGE.POD") == clean_language_hash
            assert not (game / "dinput8.dll").exists()
            assert not (fake_project / "test_backup" / "menu_probe" / "restore_manifest.json").exists()
        print("PASS: mismatched DLL/POD/EXE rejected before writes")


if __name__ == "__main__":
    main()
