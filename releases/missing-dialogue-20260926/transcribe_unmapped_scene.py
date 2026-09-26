from pathlib import Path
import csv
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / '_cn_project/tools'))
from pod3 import Pod3File
from faster_whisper import WhisperModel

def main():
    videos = {m.group(1) for path in (ROOT / 'video').glob('*_RU.srt')
              if (m := re.match(r'(A\dS\d{2})', path.name))}
    with (HERE / 'audio_audit.tsv').open(encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream, delimiter='\t'))
    targets = []
    for row in rows:
        if row['status'] != 'no_english_script_key_audio_or_unmapped':
            continue
        name = row['audio_name'].rsplit('\\', 1)[-1]
        match = re.match(r'A(\d)S(\d+)_', name)
        if match and f'A{match.group(1)}S{int(match.group(2)):02d}' not in videos:
            targets.append(row['audio_name'])
    sounds = Pod3File(ROOT / 'W32ENSND.POD')
    model = WhisperModel('small', device='cpu', compute_type='int8', local_files_only=True)
    temp = HERE / '_asr_temp.wav'
    with (HERE / 'unmapped_scene_asr.tsv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream, delimiter='\t')
        writer.writerow(['audio_name', 'asr_en', 'duration_sec', 'review'])
        for number, name in enumerate(targets, 1):
            temp.write_bytes(sounds.read_entry(name))
            segments, info = model.transcribe(str(temp), beam_size=5, language='en', vad_filter=False)
            segments = list(segments)
            text = ' '.join(s.text.strip() for s in segments).strip()
            writer.writerow([name, text, round(info.duration, 2), 'ASR only; confirm before translation'])
            stream.flush()
            print(f'ASR {number}/{len(targets)} {name} {text!r}', flush=True)
    temp.unlink(missing_ok=True)

if __name__ == '__main__':
    main()
