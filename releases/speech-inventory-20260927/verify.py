"""Static checks for extraction completeness and unchanged source assets."""
import csv
import json
import hashlib
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def load(name):
    with (HERE / name).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def main():
    scripted = load("scripted_other_speech.tsv")
    categories = load("engine_rayne_categories.tsv")
    samples = load("engine_rayne_samples.tsv")
    assert len(scripted) == 127
    assert len(categories) == 72
    assert len(samples) == 253
    assert len({row["audio_entry"] for row in samples}) == 253
    assert all(row["english"] and row["current_chinese"] for row in scripted)
    assert all(row["asr_status"] != "not_transcribed" for row in samples)
    assert sum(int(row["english_wav_count"]) for row in categories) == 262
    ids = Counter(cue_id for row in samples for cue_id in row["cue_ids"].split(","))
    assert all(ids[row["cue_id"]] == int(row["english_wav_count"]) for row in categories if int(row["english_wav_count"]))
    for name, expected in json.loads((HERE / "source_hashes.json").read_text(encoding="utf-8")).items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest().upper() == expected, name
    print(f"MODIFIED_OK other={len(scripted)} unique_keys={len({row['key'].lower() for row in scripted})} categories={len(categories)} unique_wav={len(samples)} asr_drafts={sum(row['asr_status']=='draft_review' for row in samples)} no_speech={sum(row['asr_status']=='no_speech_detected' for row in samples)} decode_errors={sum(row['asr_status']=='decode_error' for row in samples)} sources_unchanged=yes")


if __name__ == "__main__":
    main()
