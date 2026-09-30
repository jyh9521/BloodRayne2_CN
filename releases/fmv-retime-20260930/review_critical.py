"""Large-v3 cross-check of four ambiguous onset/quiet-dialogue windows."""
from pathlib import Path
import json
from faster_whisper import WhisperModel
from faster_whisper.audio import decode_audio

HERE = Path(__file__).resolve().parent
WINDOWS = [('A2S02P16', 0, 14), ('A1S01P06', 24, 41),
           ('A4S03P04', 120, 127), ('A4S02P02', 18, 28)]


def main():
    model = WhisperModel('large-v3', device='cpu', compute_type='int8', cpu_threads=8, local_files_only=True)
    for movie, start, end in WINDOWS:
        path = HERE / 'asr' / f'{movie}_large_{start}.json'
        if path.exists():
            continue
        audio = decode_audio(str(HERE / 'audio' / f'{movie}.wav'))[start*16000:end*16000]
        segments, _ = model.transcribe(audio, language='en', word_timestamps=True, vad_filter=False, condition_on_previous_text=False, beam_size=5)
        records = []
        for s in segments:
            records.append({'start': s.start + start, 'end': s.end + start, 'text': s.text.strip(), 'words': [{'start': w.start + start, 'end': w.end + start, 'word': w.word, 'probability': w.probability} for w in s.words]})
            print(movie, start, records[-1]['start'], records[-1]['end'], records[-1]['text'], flush=True)
        path.write_text(json.dumps({'movie': movie, 'model': 'faster-whisper large-v3 int8 CPU', 'window': [start, end], 'segments': records}, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
