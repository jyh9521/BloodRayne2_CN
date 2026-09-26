"""Second-pass English ASR on ambiguous voice lines; audio is not modified."""
import csv
import io
import sys
from pathlib import Path

from faster_whisper import WhisperModel

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "_cn_project" / "tools"))
from pod3 import Pod3File

SELECT = {13, 16, 17, 19, 27, 43, 45, 47, 51, 57, 65, 80, 83, 101, 103, 105, 106, 108, 109,
          111, 116, 133, 153, 169, 204, 209, 210, 224, 237, 238, 252, 253}


def main():
    with (HERE / "voice_subtitles_zh.tsv").open(encoding="utf-8-sig", newline="") as stream:
        source = list(csv.DictReader(stream, delimiter="\t"))
    sound = Pod3File(ROOT / "W32ENSND.POD")
    model = WhisperModel("medium", device="cpu", compute_type="int8", cpu_threads=8)
    rows = []
    for number in sorted(SELECT):
        row = source[number - 1]
        segments, _ = model.transcribe(io.BytesIO(sound.read_entry(row["audio_entry"])),
                                        language="en", beam_size=5, best_of=5,
                                        condition_on_previous_text=False)
        rows.append({"number": number, "audio_entry": row["audio_entry"],
                     "small_draft": row["asr_draft_english"],
                     "medium_draft": " ".join(segment.text.strip() for segment in segments).strip(),
                     "translation_zh": row["translation_zh"]})
        print(f"REVIEW_ASR {number}/{len(source)} {rows[-1]['medium_draft']}", flush=True)
    with (HERE / "asr_comparison.tsv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), delimiter="\t", lineterminator="\r\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"REVIEW_ASR_OK clips={len(rows)}")


if __name__ == "__main__":
    main()
