"""Decode the installed Bink English tracks and obtain word-level timing evidence."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys

import av
import imageio_ffmpeg
from faster_whisper import WhisperModel

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / '_cn_project/tools'))
from build_fmv_probe import cues


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block := stream.read(4 * 1024 * 1024):
            h.update(block)
    return h.hexdigest().upper()


def main():
    for name in ('original', 'audio', 'asr', 'source', 'payload/video'):
        (HERE / name).mkdir(parents=True, exist_ok=True)
    files = sorted((ROOT / 'video').glob('*_RU.srt'))
    snapshot = HERE / 'baseline.json'
    if not snapshot.exists():
        protected = [p for p in (ROOT / 'video').iterdir() if p.is_file()]
        protected += [ROOT / n for n in ('dinput8.dll', 'rayne2.exe', 'LANGUAGE.POD', 'COMMON.POD', 'W32ART.POD', 'W32ENSND.POD')]
        hashes = {str(p.relative_to(ROOT)).replace('\\', '/'): sha(p) for p in protected}
        snapshot.write_text(json.dumps(hashes, indent=2) + '\n', encoding='utf-8')
        for p in files:
            shutil.copy2(p, HERE / 'original' / p.name)
    hashes = json.loads(snapshot.read_text())
    mapping = json.loads((ROOT / '_cn_project/releases/engine-voice-subtitles-20260927/character_map.json').read_text(encoding='utf-8'))
    inverse = {bytes((0x81 + index // 94, 0xA1 + index % 94)): char for char, index in mapping.items()}
    model = WhisperModel('medium', device='cpu', compute_type='int8', cpu_threads=8, local_files_only=True)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    for file in files:
        assert sha(file) == hashes['video/' + file.name]
        movie = file.stem[:-3]
        source = []
        for number, stamp, body in cues(file.read_bytes()):
            text, i = '', 0
            while i < len(body):
                if body[i] < 128:
                    text += chr(body[i]); i += 1
                else:
                    text += inverse[body[i:i+2]]; i += 2
            source.append({'cue': int(number), 'timestamp': stamp.decode(), 'text': text, 'bytes': len(body)})
        (HERE / 'source' / (movie + '.json')).write_text(json.dumps(source, ensure_ascii=False, indent=2), encoding='utf-8')
        result = HERE / 'asr' / (movie + '.json')
        if result.exists():
            print('ASR_REUSE ' + movie, flush=True)
            continue
        wav = HERE / 'audio' / (movie + '.wav')
        if not wav.exists():
            subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-i', str(ROOT / 'video' / (movie + '.bik')), '-map', '0:a:0', '-vn', '-ac', '1', '-ar', '16000', str(wav)], check=True)
        with av.open(str(ROOT / 'video' / (movie + '.bik'))) as container:
            duration = container.duration / 1_000_000
        segments, info = model.transcribe(str(wav), language='en', beam_size=5, best_of=5, word_timestamps=True, vad_filter=True, condition_on_previous_text=False)
        records = []
        for s in segments:
            records.append({'start': s.start, 'end': s.end, 'text': s.text.strip(), 'words': [{'start': w.start, 'end': w.end, 'word': w.word, 'probability': w.probability} for w in s.words]})
            print(f'{movie} {s.start:.2f}-{s.end:.2f} {s.text.strip()}', flush=True)
        result.write_text(json.dumps({'movie': movie, 'duration': duration, 'audio_sha256': sha(wav), 'model': 'faster-whisper medium int8 CPU', 'segments': records}, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'ASR_OK {movie} segments={len(records)} duration={duration:.3f}', flush=True)


if __name__ == '__main__':
    main()
