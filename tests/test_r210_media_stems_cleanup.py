"""YouTube publication, truthful media use and server Demucs queue regressions."""
import json
import os
from pathlib import Path
import sys
import time
import types
import wave
import pytest
from fastapi.testclient import TestClient
from app import storage,main,ai_arranger_runtime as queue,auth
from app.models import Track,Clip,ProjectClip
from app import project_media_usage as media


def wav(path):
    path.parent.mkdir(parents=True,exist_ok=True)
    with wave.open(str(path),'wb') as stream:
        stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(44100)
        stream.writeframes(bytes(8820))
    return path


@pytest.fixture
def project(tmp_path,monkeypatch):
    # Drain collectors from preceding tests before replacing their roots.
    deadline=time.monotonic()+5
    while storage._GC_ACTIVE and time.monotonic()<deadline:time.sleep(.02)
    assert not storage._GC_ACTIVE
    monkeypatch.setattr(storage,'ROOT',tmp_path/'projects')
    monkeypatch.setattr(storage,'SHARED_MEDIA_ROOT',tmp_path/'shared')
    monkeypatch.setattr(storage,'SHARED_AUDIO_ROOT',tmp_path/'shared'/'audio')
    monkeypatch.setattr(storage,'SHARED_INDEX_PATH',tmp_path/'shared'/'index.json')
    monkeypatch.setattr(queue,'_ROOT',tmp_path/'queue')
    monkeypatch.setattr(auth,'DATA_ROOT',tmp_path/'auth')
    monkeypatch.setattr(main,'MEDIA_JOBS',{})
    monkeypatch.setattr(main,'STEM_JOBS',{})
    monkeypatch.setenv('MTA_ALLOW_INSECURE_NO_AUTH','true')
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False)
    monkeypatch.setattr(main,'waveform_peaks',lambda *a,**k:[])
    monkeypatch.setattr(main,'estimate_bpm_and_signature',lambda *a:(120,'4/4'))
    return storage.create_project('Media regression')


def youtube(monkeypatch):
    class YoutubeDL:
        def __init__(self,options):self.options=options
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def extract_info(self,url,download):
            source=wav(Path(self.options['outtmpl'].replace('%(ext)s','wav')))
            return {'title':'Regression song','requested_downloads':[{'filepath':str(source)}]}
    monkeypatch.setitem(sys.modules,'yt_dlp',types.SimpleNamespace(YoutubeDL=YoutubeDL))


def run_youtube(project):
    jid='a'*16
    main.MEDIA_JOBS[jid]={'id':jid,'project_id':project.id,'status':'queued'}
    main._youtube_import_worker(jid,project.id,'https://youtu.be/dQw4w9WgXcQ','','other',0,'manual','')
    return main.MEDIA_JOBS[jid]


def test_youtube_uses_real_track_publication_receipt_and_survives_reopen(project,monkeypatch):
    youtube(monkeypatch)
    job=run_youtube(project)
    assert job['status']=='completed',job.get('error')
    reopened=storage.load_project(project.id)
    assert len(reopened.tracks)==1 and len(reopened.clip_library)==1
    assert storage.audio_path(project.id,reopened.tracks[0].filename).is_file()
    assert list(storage.originals_dir(project.id).iterdir())
    assert not list(storage.pdir(project.id).glob('.async-track-*.pending.json'))


def test_youtube_failure_removes_only_owned_audio_and_original(project,monkeypatch):
    youtube(monkeypatch)
    other=storage.original_path(project.id,'existing.bin');other.write_bytes(b'keep')
    monkeypatch.setattr(main,'_normalize_audio_to_project_rate',lambda *a:(_ for _ in ()).throw(ValueError('conversion failed')))
    assert run_youtube(project)['status']=='failed'
    assert list((storage.pdir(project.id)/'audio').iterdir())==[]
    assert other.read_bytes()==b'keep'
    assert list(storage.originals_dir(project.id).iterdir())==[other]
    assert not list(storage.pdir(project.id).glob('.async-track-*.pending.json'))


def test_reusable_clip_is_not_falsely_in_use_and_can_be_deleted(project):
    path=wav(storage.audio_path(project.id,'reusable.wav'))
    project.clip_library=[ProjectClip(id='clip1',name='Reusable',filename=path.name,duration_ms=100)]
    storage.save_project(project)
    row=next(r for r in storage.project_files(project.id) if r['name']==path.name)
    assert row['reusable'] and not row['referenced'] and not row['timeline']
    client=TestClient(main.app,headers={'x-mta-request':'1'})
    response=client.delete(f'/api/projects/{project.id}/files/audio/{path.name}')
    assert response.status_code==200,response.text
    assert not path.exists() and not storage.load_project(project.id).clip_library


def test_cleanup_preserves_timeline_original_and_queued_sources(project):
    keep=wav(storage.audio_path(project.id,'keep.wav'))
    orphan=wav(storage.audio_path(project.id,'orphan.wav'))
    library=wav(storage.audio_path(project.id,'library.wav'))
    pending=wav(storage.audio_path(project.id,'queued.wav'))
    original=storage.original_path(project.id,'original.bin');original.write_bytes(b'original')
    project.tracks=[Track(id='t',name='Keep',filename=keep.name)]
    project.clip_library=[ProjectClip(id='c',name='Unused',filename=library.name,duration_ms=100)]
    storage.save_project(project)
    queue.start(project.id,'stem-separation',lambda *a:None,job_id='b'*16,defer_spawn=True,
        payload={'source_category':'audio','source_name':pending.name})
    result=media.cleanup(project.id,remove_unused_library=True)
    assert result['library_removed']==1 and result['active_jobs']
    assert keep.exists() and pending.exists() and original.exists()
    assert not library.exists() and not orphan.exists()
    with pytest.raises(ValueError,match='pending job'):
        storage.delete_project_file(project.id,'audio',pending.name)
    with queue._db() as con:con.execute("UPDATE jobs SET state='cancelled' WHERE job_id=?",('b'*16,))
    media.cleanup(project.id)
    assert not pending.exists() and keep.exists()


def test_cleanup_does_not_delete_uncommitted_import_or_recent_temp(project):
    from app.ai_async_track_transaction import begin,reconcile
    name='1234567890.wav';jid='c'*16
    begin(project.id,jid,name)
    pending=wav(storage.audio_path(project.id,name))
    media.cleanup(project.id)
    assert pending.exists()
    reconcile(project.id,jid)
    stale=storage.pdir(project.id)/'.project.json.old.tmp';stale.write_bytes(b'temp')
    fresh=storage.pdir(project.id)/'.project.json.fresh.tmp';fresh.write_bytes(b'temp')
    os.utime(stale,(1,1))
    result=media.cleanup(project.id)
    assert result['temporary_deleted']==1 and fresh.exists() and not stale.exists()


def test_malformed_media_journal_prevents_destructive_cleanup(project):
    orphan=wav(storage.audio_path(project.id,'orphan.wav'))
    (storage.pdir(project.id)/('.async-track-'+'d'*16+'.pending.json')).write_text('{broken')
    with pytest.raises(ValueError,match='journal'):media.cleanup(project.id,remove_unused_library=True)
    assert orphan.exists()


def test_legacy_job_reservation_is_released_at_termination(project):
    path=wav(storage.audio_path(project.id,'library.wav'))
    project.clip_library=[ProjectClip(id='c',name='Reusable',filename=path.name,duration_ms=100)]
    storage.save_project(project)
    queue.start(project.id,'arranger',lambda *a:None,job_id='e'*16,defer_spawn=True)
    media.cleanup(project.id,remove_unused_library=True)
    assert path.exists() and storage.project_files(project.id)[0]['pending_job']
    with queue._db() as con:con.execute("UPDATE jobs SET state='cancelled' WHERE job_id=?",('e'*16,))
    row=storage.project_files(project.id)[0]
    assert row['reusable'] and not row['referenced']
    media.cleanup(project.id,remove_unused_library=True)
    assert not path.exists()


def test_cleanup_api_requires_integrity_and_explicit_policy(project):
    client=TestClient(main.app)
    path=f'/api/projects/{project.id}/files/cleanup'
    assert client.post(path,json={'remove_unused_library':True}).status_code==403
    assert client.post(path,json={},headers={'x-mta-request':'1'}).status_code==400
    assert client.post(path,json={'remove_unused_library':False},headers={'x-mta-request':'1'}).status_code==200


def test_external_demucs_runtime_and_gpu_device_are_forwarded(tmp_path,monkeypatch):
    from app.plugins import DemucsStemSplitter
    from app import demucs_runtime
    python=tmp_path/'python';captured=tmp_path/'args.json'
    python.write_text('#!'+sys.executable+'\nimport sys,json,pathlib,wave\n'
      'if "-c" in sys.argv:sys.exit(0)\n'
      f'pathlib.Path({str(captured)!r}).write_text(json.dumps(sys.argv))\n'
      'args=sys.argv;out=pathlib.Path(args[args.index("--out")+1])/args[args.index("-n")+1]/pathlib.Path(args[-1]).stem;out.mkdir(parents=True)\n'
      'with wave.open(str(out/"vocals.wav"),"wb") as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(44100);w.writeframes(bytes(882))\n')
    python.chmod(0o755)
    monkeypatch.setenv('MTA_DEMUCS_PYTHON',str(python));monkeypatch.setenv('MTA_DEMUCS_DEVICE','cuda')
    demucs_runtime._installed.cache_clear()
    assert DemucsStemSplitter.status()['available']
    source=wav(tmp_path/'source.wav')
    paths=DemucsStemSplitter.split(source,tmp_path/'out')
    args=json.loads(captured.read_text())
    assert args[1:3]==['-m','demucs.separate'] and args[args.index('--device')+1]=='cuda'
    assert len(paths)==1 and paths[0].is_file()
    from app.ai_unified_adapter import _backend_command
    monkeypatch.setenv('MTA_AI_TORCH_PROFILER_ENABLED','false')
    assert _backend_command({},tmp_path,'demucs',[])[0]==str(python)


@pytest.mark.parametrize('remote',[False,True])
def test_web_track_separation_is_queued_and_publishes_stems(project,monkeypatch,tmp_path,remote):
    source=wav(storage.audio_path(project.id,'source.wav'))
    project.tracks=[Track(id='t',name='Source',filename=source.name,duration_ms=100,
        clips=[Clip(id='x',source_end_ms=100)])]
    storage.save_project(project)
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',remote)
    from app import native_ai_routing
    monkeypatch.setattr(native_ai_routing,'is_remote',lambda kind:remote)
    monkeypatch.setattr(main.STEM_SPLITTER,'available',lambda:not remote)
    assert main._stem_runtime_status()['available']
    if remote:
        data=wav(tmp_path/'remote.wav').read_bytes()
        monkeypatch.setattr(main,'_native_remote_infer',lambda *a,**k:({'audio':{'stem_vocals.wav':data,'stem_drums.wav':data}},'remote-job'))
    def split(source,out,**kw):
        return [wav(out/'vocals.wav'),wav(out/'drums.wav')]
    monkeypatch.setattr(main.STEM_SPLITTER,'split',split)
    pending=[]
    monkeypatch.setattr(queue,'_spawn',lambda jid,fn,**kw:pending.append((jid,fn)))
    client=TestClient(main.app,headers={'x-mta-request':'1'})
    result=client.post(f'/api/projects/{project.id}/tracks/t/stem-jobs')
    assert result.status_code==200,result.text
    jid=result.json()['id']
    assert queue.get(jid)['operation']=='stem-separation'
    assert queue.get(jid)['state']=='queued' and pending
    storage.promote_project_audio_to_shared(project.id)
    with queue._db() as con:payload=json.loads(con.execute('SELECT payload_json FROM jobs WHERE job_id=?',(jid,)).fetchone()[0])
    assert callable(main._restore_stem_split_job(project.id,payload,jid))
    pending[0][1](tmp_path/'progress.json')
    assert main.STEM_JOBS[jid]['status']=='completed',main.STEM_JOBS[jid].get('error')
    reopened=storage.load_project(project.id)
    assert len(reopened.tracks)==3
    assert all(storage.audio_path(project.id,t.filename).is_file() for t in reopened.tracks)


def test_horizontal_import_removed_but_sidebar_picker_preserved():
    root=Path(__file__).resolve().parents[1]
    js=(root/'app/static/app.js').read_text();html=(root/'app/templates/index.html').read_text()
    assert '♫ Import Audio Track</button>' not in js
    assert 'id="newTrackFile" type="file" hidden' in js
    assert 'onclick="focusImport()"' in html


def test_signed_server_builds_include_demucs_setup():
    root=Path(__file__).resolve().parents[1]
    for name in ('build_deb.sh','build_rpm.sh'):
        assert 'native-installers/install_demucs.py' in (root/'scripts/server_packages'/name).read_text()


def test_file_link_cannot_delete_another_referenced_media(project):
    keep=wav(storage.audio_path(project.id,'keep.wav'))
    project.tracks=[Track(id='t',name='Keep',filename=keep.name)]
    storage.save_project(project)
    (storage.pdir(project.id)/'audio'/'alias.wav').symlink_to(keep)
    with pytest.raises(ValueError,match='link'):
        storage.delete_project_file(project.id,'audio','alias.wav')
    assert keep.exists()


def test_only_verified_content_addressed_hardlinks_are_trusted(project,tmp_path):
    path=wav(storage.audio_path(project.id,'source.wav'))
    os.link(path,tmp_path/'untrusted.wav')
    assert not storage.verified_shared_audio(path)
    project.tracks=[Track(id='t',name='Source',filename=path.name)]
    storage.save_project(project)
    storage.promote_project_audio_to_shared(project.id)
    assert storage.verified_shared_audio(path)
    # Editing the shared inode invalidates its content-addressed identity.
    path.write_bytes(b'changed')
    assert not storage.verified_shared_audio(path)


def test_cleanup_account_acl_denies_foreign_project(project,monkeypatch):
    project.owner_user_id=123
    storage.save_project(project)
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH')
    auth.init_auth_db()
    with auth.db() as con:
        con.execute("INSERT INTO users(username,email,password_hash,active,email_confirmed,role,created_at,updated_at) VALUES('foreign','foreign@example.com','unused',1,1,'user',1,1)")
        identity=dict(con.execute("SELECT * FROM users WHERE username='foreign'").fetchone())
    monkeypatch.setattr(main,'session_user',lambda request:identity)
    client=TestClient(main.app,headers={'x-mta-request':'1'})
    response=client.post(f'/api/projects/{project.id}/files/cleanup',json={'remove_unused_library':True})
    assert response.status_code==404  # Deliberately hide foreign project existence.


def test_demucs_installer_preserves_accelerator_versions_and_configuration(tmp_path,monkeypatch):
    import importlib.util
    import subprocess
    root=Path(__file__).resolve().parents[1]
    spec=importlib.util.spec_from_file_location('demucs_installer',root/'scripts/install_demucs.py')
    installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)
    executable=tmp_path/'python';executable.write_text('');executable.chmod(0o755)
    env=tmp_path/'mta.env';env.write_text('MTA_PORT=8081\nMTA_DEMUCS_DEVICE=cpu\n')
    calls=[]
    def run(args,**kw):
        calls.append(args)
        if '--constraint' in args:
            constraints=Path(args[args.index('--constraint')+1]).read_text()
            assert constraints=='torch==2.11.0+rocm7.2.4\ntorchaudio==2.11.0+rocm7.2.4\ntransformers==4.57.0\n'
        if '--format=json' in args:return subprocess.CompletedProcess(args,0,json.dumps([{'name':'transformers','version':'4.57.0'}]),'')
        return subprocess.CompletedProcess(args,0,'torch==2.11.0+rocm7.2.4\ntorchaudio==2.11.0+rocm7.2.4\n','')
    monkeypatch.setattr(installer.subprocess,'run',run)
    installer.install(str(executable),env)
    assert 'MTA_PORT=8081' in env.read_text() and 'MTA_DEMUCS_DEVICE="auto"' in env.read_text()
    assert env.stat().st_mode&0o777==0o600
    assert 'MTA_AI_WORKER_DEMUCS_EXECUTABLE=' in env.read_text()
    assert 'MTA_AI_WORKER_ENABLED="true"' in env.read_text()
    assert len(calls)==4
    def changed(args,**kw):
        result=run(args,**kw)
        if 'import demucs.separate' in args[-1]:env.write_text('MTA_PORT=9090\n')
        return result
    monkeypatch.setattr(installer.subprocess,'run',changed)
    with pytest.raises(ValueError,match='configuration changed'):installer.install(str(executable),env)
    assert env.read_text()=='MTA_PORT=9090\n'
    before=env.read_bytes()
    monkeypatch.setattr(installer.subprocess,'run',lambda *a,**k:(_ for _ in ()).throw(subprocess.CalledProcessError(1,['pip'])))
    with pytest.raises(subprocess.CalledProcessError):installer.install(str(executable),env)
    assert env.read_bytes()==before
