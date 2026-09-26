"""Produce reviewable unified diffs from the preserved previous inventory."""
import difflib
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "start-say-subtitles-20260926" / "engine_cue_inventory.tsv"
parts = []
for before, after in (
    (OLD, HERE / "engine_rayne_categories.tsv"),
    (None, HERE / "scripted_other_speech.tsv"),
    (None, HERE / "engine_rayne_samples.tsv"),
):
    left = before.read_text(encoding="utf-8-sig").splitlines(keepends=True) if before else []
    right = after.read_text(encoding="utf-8-sig").splitlines(keepends=True)
    parts.extend(difflib.unified_diff(left, right, fromfile=str(before or "/dev/null"), tofile=str(after), lineterm="\n"))
(HERE / "DIFF_FILE.diff").write_text("".join(parts), encoding="utf-8")
print(f"DIFF_OK sections=3 lines={sum(1 for line in parts if line.startswith('@@'))}")
