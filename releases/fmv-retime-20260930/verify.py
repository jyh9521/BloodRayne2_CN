"""Read-only validation of baseline, rebuilt subtitles, installation, rollback."""
from pathlib import Path
import argparse
import hashlib
import json
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'_cn_project/tools'))
from build_fmv_probe import cues


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block:=stream.read(4*1024*1024): h.update(block)
    return h.hexdigest().upper()


def ms(s):
    h,m,tail=s.split(':');sec,milli=tail.split(',')
    return int(h)*3600000+int(m)*60000+int(sec)*1000+int(milli)


def stats(blob,duration):
    previous_end=-1;overlaps=overflow=0
    cc=cues(blob)
    for number,timestamp,body in cc:
        start,end=[ms(s) for s in timestamp.decode().split(' --> ')]
        assert 0 <= start < end
        overlaps+=start<previous_end
        overflow+=end>round(duration*1000)
        previous_end=end
    return len(cc),overlaps,overflow


def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['baseline','modified','installed','rollback']);parser.add_argument('--root',type=Path)
    args=parser.parse_args();baseline=json.loads((HERE/'baseline.json').read_text())
    originals=sorted((HERE/'original').glob('*_RU.srt'))
    if args.mode=='rollback':
        assert args.root
        for file in originals: assert sha(args.root/'video'/file.name)==baseline['video/'+file.name],file.name
        print('ROLLBACK_OK files=15 original_hashes_restored=15 prior_timestamps_restored=yes text_preserved=yes')
        return
    changed_names={'video/'+f.name for f in originals}
    for name,expected in baseline.items():
        if args.mode!='baseline' and name in changed_names: continue
        assert sha(ROOT/name)==expected,name
    if args.mode=='baseline':
        count=overlaps=overflow=0
        for file in originals:
            assert sha(file)==baseline['video/'+file.name]
            duration=json.loads((HERE/'asr'/f'{file.stem[:-3]}.json').read_text())['duration']
            c,o,f=stats(file.read_bytes(),duration);count+=c;overlaps+=o;overflow+=f
        print(f'BASELINE_OK movies={len(originals)} cues={count} overlaps={overlaps} out_of_video={overflow} original_hashes=ok')
        return
    manifest=json.loads((HERE/'manifest.json').read_text());count=overlaps=overflow=0
    for movie in manifest['movies']:
        name=movie['movie']+'_RU.srt';original=(HERE/'original'/name).read_bytes();payload=HERE/'payload/video'/name
        assert sha(payload)==movie['after']
        modified=payload.read_bytes()
        assert len(original)==len(modified)
        before=cues(original);after=cues(modified)
        assert [(n,b) for n,t,b in before]==[(n,b) for n,t,b in after],name
        c,o,f=stats(modified,movie['duration']);count+=c;overlaps+=o;overflow+=f
        if args.mode=='installed': assert sha(ROOT/'video'/name)==movie['after'],name
    assert count==222 and overlaps==0 and overflow==0
    label='INSTALLED_OK' if args.mode=='installed' else 'MODIFIED_OK'
    print(f'{label} movies=15 cues=222 text_bytes_unchanged=222 overlaps=0 out_of_video=0 protected_assets=unchanged')


if __name__=='__main__': main()
