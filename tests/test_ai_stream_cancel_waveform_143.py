from pathlib import Path
import threading

ROOT=Path(__file__).resolve().parents[1]


def test_ai_model_buttons_are_native_safe_and_downloads_have_progress_jobs():
    js=(ROOT/'app/static/app.js').read_text(encoding='utf-8')
    css=(ROOT/'app/static/app.css').read_text(encoding='utf-8')
    main=(ROOT/'app/main.py').read_text(encoding='utf-8')
    assert 'ai-model-action-btn' in js
    assert '-webkit-text-fill-color:#f4fbff!important' in css
    assert '/download-jobs' in js
    assert 'pollModelDownloadJob' in js
    assert '@app.post("/api/ai-models/lyrics/{model_id}/download-jobs")' in main
    assert '@app.post("/api/ai-models/chords/{model_id}/download-jobs")' in main
    assert 'stem-progress.indeterminate' in css


def test_text_extraction_jobs_stream_partial_results_and_can_cancel():
    js=(ROOT/'app/static/app.js').read_text(encoding='utf-8')
    main=(ROOT/'app/main.py').read_text(encoding='utf-8')
    music=(ROOT/'app/music_text.py').read_text(encoding='utf-8')
    assert 'mediaPartialText(job)' in js
    assert 'Annulla estrazione' in js
    assert '/api/media-jobs/${jobId}/cancel' in js
    assert '@app.post("/api/media-jobs/{job_id}/cancel")' in main
    assert 'extract_lyrics_progressive' in music
    assert 'extract_chords_progressive' in music
    assert 'cancel_event' in main


def test_waveform_is_dense_per_visible_pixel_not_limited_to_cached_bins():
    js=(ROOT/'app/static/app.js').read_text(encoding='utf-8')
    start=js.index('async function drawWave(t){')
    end=js.index('\nfunction ',start+10)
    draw=js[start:end]
    assert 'columns=Math.max(1,Math.ceil(tw))' in draw
    assert 'zoomed in columns interpolate between cached bins' in draw
    assert 'Math.min(Math.ceil(tw),sourceBins)' not in draw


def test_madmom_input_is_canonical_pcm_wav(monkeypatch,tmp_path):
    import app.music_text as mt
    calls=[]
    def fake_run(cmd):
        calls.append(cmd)
        Path(cmd[-1]).write_bytes(b'RIFF'+b'0'*64)
        return ''
    monkeypatch.setattr(mt,'_run',fake_run)
    src=tmp_path/'song.m4a';src.write_bytes(b'\x00\x00\x00\x1cftypM4A ')
    out=tmp_path/'analysis.wav'
    assert mt._madmom_pcm_wav(src,out)==out
    assert calls and calls[0][0]=='ffmpeg'
    assert 'pcm_s16le' in calls[0]
    assert out.read_bytes().startswith(b'RIFF')


def test_ai_accelerator_prefers_cuda_then_cpu(monkeypatch):
    import sys, types
    import app.music_text as mt
    fake=types.SimpleNamespace(cuda=types.SimpleNamespace(is_available=lambda: True),backends=types.SimpleNamespace(mps=types.SimpleNamespace(is_available=lambda: False)))
    monkeypatch.setitem(sys.modules,'torch',fake)
    monkeypatch.delenv('MTA_AI_DEVICE',raising=False)
    assert mt.native_ai_device()=='cuda'
    monkeypatch.setitem(sys.modules,'torch',types.SimpleNamespace(cuda=types.SimpleNamespace(is_available=lambda: False),backends=types.SimpleNamespace(mps=types.SimpleNamespace(is_available=lambda: False))))
    assert mt.native_ai_device()=='cpu'


def test_media_job_public_exposes_cancel_and_partial():
    import app.main as main
    event=threading.Event()
    job={'id':'x','kind':'extract-lyrics','project_id':'p','status':'running','progress':42,'message':'x','created_at':1.0,'updated_at':2.0,'result':None,'error':None,'partial':{'kind':'lyrics','items':[{'text':'ciao'}]},'cancel_event':event}
    public=main._media_job_public(job)
    assert public['cancel_supported'] is True
    assert public['cancel_requested'] is False
    assert public['partial']['items'][0]['text']=='ciao'
    event.set()
    assert main._media_job_public(job)['cancel_requested'] is True


def test_progressive_lyrics_chunks_and_reports(monkeypatch,tmp_path):
    import sys, types
    import app.music_text as mt
    class Model:
        def transcribe(self,path,**kwargs):
            return {'segments':[{'start':0.0,'end':1.0,'text':'hello','words':[]}]}
    fake=types.SimpleNamespace(load_model=lambda *a,**k: Model())
    monkeypatch.setitem(sys.modules,'whisper',fake)
    real_find=mt.importlib.util.find_spec
    monkeypatch.setattr(mt.importlib.util,'find_spec',lambda name: object() if name=='whisper' else real_find(name))
    monkeypatch.setattr(mt,'native_ai_device',lambda:'cpu')
    monkeypatch.setattr(mt,'_duration_seconds',lambda path:61.0)
    def fake_run(cmd):
        if cmd[0]=='ffmpeg': Path(cmd[-1]).write_bytes(b'RIFF')
        return ''
    monkeypatch.setattr(mt,'_run',fake_run)
    updates=[]
    rows=mt.extract_lyrics_progressive(tmp_path/'song.mp3',model_name='tiny',progress=lambda p,i,m:updates.append((p,len(i),m)),chunk_seconds=30)
    assert len(rows)==1
    assert rows[0].time_ms==0
    assert updates[-1][0]>=94
    assert updates[-1][1] in (0,1)


def test_progressive_lyrics_cancelled_before_cli_fallback(monkeypatch,tmp_path):
    import app.music_text as mt
    real_find=mt.importlib.util.find_spec
    monkeypatch.setattr(mt.importlib.util,'find_spec',lambda name: None if name=='whisper' else real_find(name))
    try:
        mt.extract_lyrics_progressive(tmp_path/'x.mp3',cancelled=lambda:True)
    except InterruptedError:
        pass
    else:
        raise AssertionError('expected cancellation')


def test_progressive_madmom_runs_one_full_pass_without_inline_events(monkeypatch,tmp_path):
    import app.music_text as mt
    class Proc:
        def __call__(self,path):
            return [(0.0,1.0,'C:maj'),(1.0,2.0,'G:maj')]
    monkeypatch.setattr(mt,'_madmom_processor',lambda engine:(Proc(),'cuda'))
    monkeypatch.setattr(mt,'extract_chords',lambda path,engine=None:[mt.Chord(time_ms=0,chord='C'),mt.Chord(time_ms=1000,chord='G')])
    updates=[]
    rows=mt.extract_chords_progressive(tmp_path/'song.m4a',engine='madmom-cnn-crf',progress=lambda p,i,m:updates.append((p,len(i),m)),chunk_seconds=30)
    assert [(x.time_ms,x.chord) for x in rows]==[(0,'C'),(1000,'G')]
    assert all(count == 0 for _, count, _ in updates)
    assert any('cuda' in msg for _,_,msg in updates)


def test_madmom_rows_and_non_ai_progressive_path(monkeypatch,tmp_path):
    import app.music_text as mt
    rows=mt._madmom_rows_to_events([(0.0,1.0,'C:maj'),(0.5,1.0,'C:maj'),(1.0,2.0,'A:min')],500)
    assert [(x.time_ms,x.chord) for x in rows]==[(500,'C'),(1500,'Am')]
    monkeypatch.setattr(mt,'extract_chords',lambda path,engine=None:[mt.Chord(time_ms=0,chord='F')])
    updates=[]
    out=mt.extract_chords_progressive(tmp_path/'x.wav',engine='mta-chromagram',progress=lambda p,i,m:updates.append(p))
    assert out[0].chord=='F' and updates[0]==8 and updates[-1]==96 and len(updates)>=5


def test_ai_catalog_reports_hardware_acceleration(monkeypatch):
    import sys, types
    import app.ai_models as am
    fake=types.SimpleNamespace(cuda=types.SimpleNamespace(is_available=lambda:True,get_device_name=lambda i:'Test GPU'),backends=types.SimpleNamespace(mps=types.SimpleNamespace(is_available=lambda:False)))
    monkeypatch.setitem(sys.modules,'torch',fake)
    monkeypatch.delenv('MTA_AI_DEVICE',raising=False)
    info=am._accelerator_info()
    assert info['hardware_accelerated'] is True and 'Test GPU' in info['device']
    monkeypatch.setenv('MTA_AI_DEVICE','cpu')
    assert am._accelerator_info()['hardware_accelerated'] is False


def test_ai_model_download_worker_success_and_failure(monkeypatch):
    import app.main as main
    base={'id':'job','kind':'download-lyrics-model','project_id':None,'status':'queued','progress':3,'message':'q','created_at':1.0,'updated_at':1.0,'result':None,'error':None}
    main.MEDIA_JOBS['job']=dict(base)
    monkeypatch.setattr(main,'download_lyrics_model',lambda model_id,native=False:{'id':model_id,'installed':True})
    main._ai_model_download_worker('job','lyrics','tiny')
    assert main.MEDIA_JOBS['job']['status']=='completed' and main.MEDIA_JOBS['job']['progress']==100
    main.MEDIA_JOBS['job2']=dict(base,id='job2')
    def boom(*a,**k): raise RuntimeError('download failed')
    monkeypatch.setattr(main,'download_chord_model',boom)
    main._ai_model_download_worker('job2','chords','madmom-cnn-crf')
    assert main.MEDIA_JOBS['job2']['status']=='failed' and 'download failed' in main.MEDIA_JOBS['job2']['error']
