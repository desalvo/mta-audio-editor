"""Explicit installation of pinned CC0 OddVoices banks; never user executable code."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

VOICES={'air':'Air Navier (alto)','cicada':'Cicada Lumen (baritone)','quake':'Quake Chesnokov (bass)'}


def root():
    from .studio_catalog import root as studio_root
    path=studio_root()/'oddvoices'
    if path.is_symlink():raise ValueError('Unsafe voicebank directory')
    path.mkdir(mode=0o700,exist_ok=True)
    return path


def manifest():
    return json.loads((Path(__file__).parent/'studio_assets/oddvoices_assets.json').read_text())


def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def bank(voice):
    if voice not in VOICES:raise ValueError('Unknown reviewed voicebank')
    folder=root();receipt=folder/(voice+'.json');target=folder/(voice+'.voice');dictionary=folder/'cmudict-0.7b'
    if any(p.is_symlink() for p in (receipt,target,dictionary)):raise ValueError('Unsafe voicebank path')
    if not receipt.is_file() or receipt.stat().st_size>32768:raise ValueError('Voicebank not installed')
    value=json.loads(receipt.read_text())
    if (value.get('voice')!=voice or value.get('source_commit')!=manifest()['commit'] or value.get('tested') is not True
            or not target.is_file() or not 1000<target.stat().st_size<512*1024*1024
            or digest(target)!=value.get('sha256') or not dictionary.is_file()
            or digest(dictionary)!=manifest()['files']['cmudict-0.7b']['sha256']):raise ValueError('Voicebank integrity failed')
    return target,dictionary


def status():
    result=[]
    for voice,name in VOICES.items():
        try:
            target,_=bank(voice);installed=True;size=target.stat().st_size;error=''
        except (ValueError,OSError) as exc:installed=False;size=0;error=str(exc)
        result.append({'id':voice,'name':name,'installed':installed,'size_bytes':size,'error':error,
            'license':'CC0-1.0 recordings / Apache-2.0 engine','languages':['en','vocalise'],
            'backend':'oddvoices-concatenative','neural':False,'devices':['cpu']})
    return result


def compile_bank(source,target,cancelled,progress):
    """Read small analysis windows instead of loading an entire recording as float64.

    Runs under the installation lock. The compiler is our pinned vendored code;
    downloaded assets contain WAV/text/JSON only, with hashes checked first.
    """
    vendor=Path(__file__).resolve().parent.parent/'native/third_party/oddvoices/python'
    sys.path.insert(0,str(vendor))
    import oddvoices.corpus as corpus
    import soundfile as sf
    class Windows:
        def __init__(self,path):self.file=sf.SoundFile(path)
        def __getitem__(self,item):
            if cancelled():raise RuntimeError('Voicebank installation cancelled')
            if not isinstance(item,slice) or item.step not in (None,1):raise ValueError('Unsupported audio analysis window')
            start,end,_=item.indices(len(self.file))
            if end-start>self.file.samplerate*10:raise ValueError('Oversized audio analysis window')
            self.file.seek(start);return self.file.read(max(0,end-start),dtype='float64')
    audio=Windows(source/'audio.wav')
    try:analyzer=corpus.CorpusAnalyzer(source,audio_source=(audio,audio.file.samplerate))
    except BaseException:
        audio.file.close();raise
    process=analyzer.process_segment;done=0;total=len(analyzer.markers)
    def segment(key):
        nonlocal done
        if cancelled():raise RuntimeError('Voicebank installation cancelled')
        value=process(key);done+=1;progress('compiling',done,total);return value
    analyzer.process_segment=segment
    try:
        database=analyzer.render_database()
        with target.open('xb') as output:corpus.write_voice_file(output,database);output.flush();os.fsync(output.fileno())
    finally:audio.file.close()


def install(voice,cancelled,progress):
    from .ai_project_lock import project_publication_lock
    from .secure_https import https_urlopen
    from .storage import _atomic_json_write
    from .fs_durability import sync_directory
    if voice not in VOICES:raise ValueError('Unknown reviewed voicebank')
    with project_publication_lock('studio-model:oddvoices'):
        folder=root();data=manifest()
        if (folder/(voice+'.voice')).exists() or (folder/(voice+'.json')).exists():
            existing,dictionary=bank(voice)
            from .vocal_synthesis import self_test
            progress('testing',0,0);return {'voice':voice,'already_installed':True,**self_test(existing,dictionary)}
        with tempfile.TemporaryDirectory(prefix='.install-',dir=folder) as raw:
            work=Path(raw)
            for name in ['cmudict-0.7b',*[f'voices/{voice}/{n}' for n in ('audio.wav','labels.txt','database.json')]]:
                if cancelled():raise RuntimeError('Voicebank installation cancelled')
                entry=data['files'][name];target=work/Path(name).name
                url='https://gitlab.com/oddvoices/oddvoices/-/raw/'+data['commit']+'/'+name
                for attempt in range(3):
                    with https_urlopen(url,timeout=90) as inp,target.open('wb') as out:
                        done=0
                        while chunk:=inp.read(1024*1024):
                            if cancelled():raise RuntimeError('Voicebank installation cancelled')
                            done+=len(chunk)
                            if done>entry['bytes']:raise ValueError('Voicebank asset exceeds pinned size')
                            out.write(chunk);progress('downloading '+Path(name).name,done,entry['bytes'])
                        out.flush();os.fsync(out.fileno())
                    if done==entry['bytes']:break
                    if attempt<2:progress('retrying truncated download',attempt+1,3)
                if target.stat().st_size!=entry['bytes'] or digest(target)!=entry['sha256']:
                    raise ValueError(f"Voicebank integrity mismatch: {name}; received {target.stat().st_size}/{entry['bytes']} bytes")
            target=work/(voice+'.voice');compile_bank(work,target,cancelled,progress)
            from .vocal_synthesis import self_test
            progress('testing',0,0);self_test(target,work/'cmudict-0.7b')
            if cancelled():raise RuntimeError('Voicebank installation cancelled before activation')
            receipt={'voice':voice,'source_commit':data['commit'],'sha256':digest(target),'tested':True,'license':'CC0-1.0'}
            for name in (voice+'.voice','cmudict-0.7b'):
                if (folder/name).is_symlink():raise ValueError('Unsafe voicebank publication path')
                os.replace(work/name,folder/name)
            sync_directory(folder);_atomic_json_write(folder/(voice+'.json'),receipt)
            return receipt


def uninstall(voice):
    from .ai_project_lock import project_publication_lock
    from . import ai_arranger_runtime as queue
    if voice not in VOICES:raise ValueError('Unknown reviewed voicebank')
    with project_publication_lock('studio-model:oddvoices'):
        with queue._db() as con:
            if con.execute("SELECT 1 FROM jobs WHERE operation IN ('worker:studio-music','worker:vocal-synthesis') AND state IN ('running','queued','blocked') LIMIT 1").fetchone():
                raise ValueError('Wait for Studio jobs to finish or cancel them before removing a voicebank')
        target,dictionary=bank(voice);target.unlink();(root()/(voice+'.json')).unlink()
        if not any((root()/(name+'.voice')).exists() for name in VOICES):dictionary.unlink()
        return {'removed':voice,'project_audio_and_midi_preserved':True}
