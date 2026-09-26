from __future__ import annotations

from pathlib import Path

from pod3 import Pod3, rebuild_entries


ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "_cn_project" / "baseline" / "LANGUAGE.POD"
TARGET = r"WORLD\RU\0COMBAT.TXT"
ADDED = r"DATA\CODEX_REBUILD_TEST.BIN"


def main() -> None:
    source = BASELINE.read_bytes()
    baseline = Pod3(source)
    original = baseline.read_entry(TARGET)
    replacement = original + b"\r\n// replacement exceeds old capacity\r\n"
    addition = b"pod3 rebuild test"
    rebuilt = Pod3(
        rebuild_entries(
            source,
            {TARGET: replacement},
            {ADDED: addition},
        )
    )
    if rebuilt.verify_crcs():
        raise AssertionError("Rebuilt POD has CRC failures")
    if rebuilt.entry_count != baseline.entry_count + 1:
        raise AssertionError("Rebuilt POD entry count mismatch")
    if rebuilt.read_entry(TARGET) != replacement:
        raise AssertionError("Replacement was not rebuilt correctly")
    if rebuilt.read_entry(ADDED) != addition:
        raise AssertionError("Addition was not rebuilt correctly")
    for entry in baseline.entries:
        if entry.name == TARGET:
            continue
        if rebuilt.read_entry(entry.name) != baseline.read_entry(entry.name):
            raise AssertionError(f"Unchanged entry differs: {entry.name}")
    print("OK: arbitrary-size POD3 replacement and addition rebuild")


if __name__ == "__main__":
    main()
