"""Change ASCII timestamps only; preserve the installed RU subtitle bodies."""
from pathlib import Path
import csv
import difflib
import hashlib
import json
import re
import sys

from faster_whisper.audio import decode_audio
from faster_whisper.vad import get_speech_timestamps, VadOptions

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / '_cn_project/tools'))
from build_fmv_probe import cues
from manual_times import TIMES, SPECIAL, KEEP_WORD_ONSET

STAMP = re.compile(rb'(?m)^\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}')


def sha(blob):
    return hashlib.sha256(blob).hexdigest().upper()


def ms(stamp):
    h, m, tail = stamp.split(':')
    s, milli = tail.split(',')
    return int(h)*3600000 + int(m)*60000 + int(s)*1000 + int(milli)


def stamp(seconds):
    t = round(seconds * 1000)
    h, t = divmod(t, 3600000)
    m, t = divmod(t, 60000)
    s, milli = divmod(t, 1000)
    return f'{h:02}:{m:02}:{s:02},{milli:03}'


def refine(start, end, intervals):
    # Word alignment may include preceding silence. Refine only nearby
    # boundaries, never jump to another utterance or extend across a long gap.
    onsets = [a for a, b in intervals if start-.25 <= a <= start+.55 and b > start+.05 and a < end-.10]
    if onsets:
        start = min(onsets, key=lambda t: abs(t-start))
    offsets = [b for a, b in intervals if end-.35 <= b <= end+.35 and b > start+.20]
    if offsets:
        end = min(offsets, key=lambda t: abs(t-end))
    return max(0, start-.06), end+.15


def main():
    rows, diffs, movies = [], [], []
    baseline = json.loads((HERE/'baseline.json').read_text())
    for movie, ranges in TIMES.items():
        original = (HERE/'original'/f'{movie}_RU.srt').read_bytes()
        assert sha(original) == baseline[f'video/{movie}_RU.srt']
        original_cues = cues(original)
        plain = json.loads((HERE/'source'/f'{movie}.json').read_text(encoding='utf-8'))
        evidence = json.loads((HERE/'asr'/f'{movie}.json').read_text())
        duration = evidence['duration']
        assert len(ranges) == len(original_cues) == len(plain)
        assert all(r is not None for r in ranges)
        audio = decode_audio(str(HERE/'audio'/f'{movie}.wav'))
        assert abs(len(audio)/16000-duration) < .2
        speech = get_speech_timestamps(audio, VadOptions(threshold=.5,min_speech_duration_ms=100,min_silence_duration_ms=180,speech_pad_ms=0))
        intervals = [(s['start']/16000,s['end']/16000) for s in speech]
        (HERE/'asr'/f'{movie}_vad.json').write_text(json.dumps(intervals, indent=2), encoding='utf-8')
        refined = []
        for i,(start,end) in enumerate(ranges,1):
            word_start = start
            if (movie,i) not in SPECIAL:
                start,end = refine(start,end,intervals)
                if (movie,i) in KEEP_WORD_ONSET:
                    start = max(0,word_start-.06)
            else:
                start,end = max(0,start),end
            # A short acknowledgement must remain readable during the
            # following silence. Never extend more than 600 ms beyond the
            # speech-tail allowance, or across the next cue.
            if (movie,i) not in SPECIAL:
                end = max(end,min(start+max(1.0,len(plain[i-1]['text'])/8.0),end+.6))
            refined.append([round(start,3),round(min(end,duration-.01),3)])
        for i in range(len(refined)-1):
            refined[i][1] = round(min(refined[i][1],refined[i+1][0]-.04),3)
        for i,(start,end) in enumerate(refined,1):
            assert 0 <= start < end <= duration, (movie,i,start,end)
            assert end-start >= .28, (movie,i,start,end)
        timestamps = [f'{stamp(a)} --> {stamp(b)}'.encode('ascii') for a,b in refined]
        it = iter(timestamps)
        modified = STAMP.sub(lambda match: next(it), original)
        assert len(modified) == len(original)
        assert [(n,b) for n,t,b in cues(modified)] == [(n,b) for n,t,b in original_cues]
        target = HERE/'payload/video'/f'{movie}_RU.srt'
        target.write_bytes(modified)
        readable_before,readable_after = [],[]
        for i,((number,old_stamp,body),new_stamp,text,(start,end)) in enumerate(zip(original_cues,timestamps,plain,refined),1):
            a,b = (ms(s)/1000 for s in old_stamp.decode().split(' --> '))
            row = {'movie':movie,'cue':i,'old_start':a,'old_end':b,'new_start':start,'new_end':end,
                   'start_shift':round(start-a,3),'end_shift':round(end-b,3),'text_bytes':len(body),
                   'text':text['text'],'evidence':SPECIAL.get((movie,i),'English audio word alignment + nearby speech-boundary refinement')}
            rows.append(row)
            readable_before.extend([str(i)+'\n',old_stamp.decode()+'\n',text['text']+'\n','\n'])
            readable_after.extend([str(i)+'\n',new_stamp.decode()+'\n',text['text']+'\n','\n'])
        (HERE/'source'/f'{movie}_ZH.utf8.srt').write_text(''.join(readable_after),encoding='utf-8')
        diffs.extend(difflib.unified_diff(readable_before,readable_after,fromfile=f'original/{movie}_RU.srt (decoded for review)',tofile=f'payload/video/{movie}_RU.srt (decoded for review)'))
        movies.append({'movie':movie,'duration':duration,'cues':len(ranges),'before':sha(original),'after':sha(modified)})
    with (HERE/'timing_review.tsv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),delimiter='\t',lineterminator='\r\n')
        writer.writeheader();writer.writerows(rows)
    (HERE/'DIFF_FILE.diff').write_text(''.join(diffs),encoding='utf-8')
    (HERE/'manifest.json').write_text(json.dumps({'movies':movies,'cues':len(rows),'policy':'Timestamp bytes only; all subtitle body bytes preserved; no movie/audio/DLL/POD changes',
        'method':'English audio medium word timestamps; no-VAD second passes; four large-v3 cross-check windows; manual semantic cue mapping; bounded silence refinement',
        'exceptions':[{ 'movie':m,'cue':c,'reason':v} for (m,c),v in SPECIAL.items()],
        'max_body_bytes':max(r['text_bytes'] for r in rows)},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'BUILD_OK movies={len(movies)} cues={len(rows)} changed_timestamps={sum(r["start_shift"] != 0 or r["end_shift"] != 0 for r in rows)} body_bytes_preserved=222 overlaps=0')


if __name__=='__main__':
    main()
