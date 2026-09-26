"""Draft-transcribe engine-selected English WAVs without changing game assets."""
from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

from faster_whisper import WhisperModel

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "_cn_project" / "tools"))
from pod3 import Pod3File


def main() -> None:
    path = HERE / "engine_rayne_samples.tsv"
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    assert len(rows) == 253
    model = WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=8)
    sounds = Pod3File(ROOT / "W32ENSND.POD")
    for index, row in enumerate(rows, 1):
        if row["asr_status"] != "not_transcribed":
            continue
        try:
            segments, info = model.transcribe(
                io.BytesIO(sounds.read_entry(row["audio_entry"])), language="en",
                beam_size=3, best_of=3, condition_on_previous_text=False,
                vad_filter=False, no_speech_threshold=0.6,
            )
            segments = list(segments)
            transcript = " ".join(segment.text.strip() for segment in segments).strip()
            row["asr_draft_english"] = transcript
            row["asr_status"] = "draft_review" if transcript else "no_speech_detected"
            row["review_note"] = "machine transcript; check against audio" if transcript else "may be nonverbal or very short speech"
            if segments:
                no_speech = max(segment.no_speech_prob for segment in segments)
                if no_speech > 0.5:
                    row["review_note"] += f"; no_speech_prob={no_speech:.2f}"
        except Exception as error:  # Record which asset needs manual review.
            row["asr_status"] = "decode_error"
            row["review_note"] = f"{type(error).__name__}: {error}"
        if index % 25 == 0 or index == len(rows):
            print(f"ASR_PROGRESS {index}/{len(rows)}", flush=True)
            with path.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\r\n")
                writer.writeheader()
                writer.writerows(rows)
    print(f"ASR_DONE rows={len(rows)} draft={sum(r['asr_status']=='draft_review' for r in rows)} no_speech={sum(r['asr_status']=='no_speech_detected' for r in rows)} errors={sum(r['asr_status']=='decode_error' for r in rows)}")


if __name__ == "__main__":
    main()
