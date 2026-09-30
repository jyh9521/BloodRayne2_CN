"""Second ASR pass without VAD on music-heavy/low-voice timing windows."""
from pathlib import Path
import json
from faster_whisper import WhisperModel
from faster_whisper.audio import decode_audio

HERE = Path(__file__).resolve().parent
WINDOWS = [('A1S01P06', 27, 46), ('A1S01P06', 48, 65),
           ('A1S01P06', 78, 103), ('A1S01P06', 110, 133),
           ('A1S01P06', 136, 151), ('A1S02P04', 22, 27),
           ('A2S01P01', 59, 69), ('A2S02P16', 5, 14),
           ('A2S02P16', 27, 32), ('A2S05P12', 49, 53),
           ('A2S05P01', 97, 104), ('A3S04P02', 60, 75),
           ('A3S04P02', 96, 117), ('A4S01P01', 64, 91),
           ('A4S01P01', 90, 105), ('A4S01P01', 117, 131),
           ('A4S02P01', 27, 33), ('A4S02P02', 18, 28),
           ('A4S03P04', 80, 89)]


def main():
    model = WhisperModel('medium', device='cpu', compute_type='int8', cpu_threads=8, local_files_only=True)
    for movie, start, end in WINDOWS:
        path = HERE / 'asr' / f'{movie}_review_{start}.json'
        if path.exists():
            continue
        audio = decode_audio(str(HERE / 'audio' / f'{movie}.wav'))[start*16000:end*16000]
        segments, _ = model.transcribe(audio, language='en', word_timestamps=True, vad_filter=False, condition_on_previous_text=True, beam_size=5, no_speech_threshold=0.8)
        records = []
        for s in segments:
            records.append({'start': s.start + start, 'end': s.end + start, 'text': s.text.strip(), 'words': [{'start': w.start + start, 'end': w.end + start, 'word': w.word, 'probability': w.probability} for w in s.words]})
            print(movie, start, records[-1]['start'], records[-1]['end'], records[-1]['text'], flush=True)
        path.write_text(json.dumps({'movie': movie, 'window': [start, end], 'segments': records}, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
