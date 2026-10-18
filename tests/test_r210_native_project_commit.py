"""Real native archive writes, Windows-compatible fsync and destination rollback."""
import errno
import json
from pathlib import Path
import stat
import sys
from types import SimpleNamespace
import zipfile

import pytest
from app import storage
from native import mta_audio_editor_native as launcher


@pytest.fixture
def workspace(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'ROOT',tmp_path/'workspace')
    storage.ROOT.mkdir()
    monkeypatch.setattr(launcher,'_data_root',lambda:tmp_path/'native')
    return storage.create_project('Progetto caffè',target='DAW',sample_rate=48000)


def require_writable_fsync(monkeypatch):
    """Enforce the Windows write-access requirement without skipping POSIX CI."""
    real_open=Path.open;real_fsync=storage.os.fsync;modes={};synced=[]
    def opened(path,*args,**kwargs):
        stream=real_open(path,*args,**kwargs)
        modes[stream.fileno()]=stream.writable()
        return stream
    def fsync(fd):
        if stat.S_ISREG(storage.os.fstat(fd).st_mode):
            if not modes.get(fd,False):
                raise PermissionError(errno.EACCES,'Windows flush requires a writable handle')
            synced.append(fd)
        return real_fsync(fd)
    monkeypatch.setattr(Path,'open',opened)
    monkeypatch.setattr(storage.os,'fsync',fsync)
    return synced


def test_archive_fsync_uses_writable_handle(workspace,tmp_path,monkeypatch):
    synced=require_writable_fsync(monkeypatch)
    target=tmp_path/'portable.maeprojz'
    storage.write_project_archive(workspace.id,target)
    assert synced
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
        assert json.loads(z.read('project/project.json'))['id']==workspace.id


def test_binding_failure_retains_previous_destination(workspace,tmp_path,monkeypatch):
    api=launcher.NativeApi();old=tmp_path/'old.maeprojz';new=tmp_path/'new.maeprojz'
    api.bind_project_path(workspace.id,str(old))
    before=api._project_paths_file.read_bytes()
    def fail(*a):raise PermissionError('Archive write denied')
    monkeypatch.setattr(api,'_write_bound_project',fail)
    with pytest.raises(PermissionError):api.bind_project_path(workspace.id,str(new))
    assert api.project_paths[workspace.id]==old
    assert api._project_paths_file.read_bytes()==before
    assert old.is_file() and not new.exists()


@pytest.mark.parametrize('shape',['winforms-tuple','cocoa-tuple','gtk-list','qt-tuple','legacy-string'])
def test_choose_create_bind_sync_reopen_real_archive(workspace,tmp_path,monkeypatch,shape):
    from native import gui_dialogs
    target=tmp_path/'Progetti caffè'/'Brano uno.maeprojz'
    returns=[str(target)] if shape=='gtk-list' else str(target) if shape=='legacy-string' else (str(target),)
    monkeypatch.setitem(sys.modules,'webview',SimpleNamespace(FileDialog=SimpleNamespace(SAVE='save')))
    monkeypatch.setattr(gui_dialogs,'file_dialog',lambda *a,**k:returns)
    api=launcher.NativeApi();api.window=object()
    chosen=api.choose_project_save_path(workspace.title)
    assert chosen['ok'] and not chosen['cancelled']
    require_writable_fsync(monkeypatch)
    bound=api.bind_project_path(workspace.id,chosen['path'])
    assert bound['ok'] and bound['portable']
    workspace.title='Saved after creation';storage.save_project(workspace)
    assert api.sync_project(workspace.id)['ok']
    restarted=launcher.NativeApi()
    assert restarted.get_project_path(workspace.id)['path']==str(target)
    reopened=restarted.open_recent_project(workspace.id)
    assert reopened['ok'] and reopened['project']['title']==workspace.title
    with zipfile.ZipFile(target) as z:
        data=json.loads(z.read('project/project.json'))
        assert data['title']==workspace.title and data['sample_rate']==48000
    assert not list(target.parent.glob('.*.tmp'))


def test_failed_flush_preserves_prior_archive_and_binding(workspace,tmp_path,monkeypatch):
    api=launcher.NativeApi();target=tmp_path/'saved.maeprojz'
    api.bind_project_path(workspace.id,str(target))
    old=target.read_bytes();registry=api._project_paths_file.read_bytes()
    workspace.title='Unsaved change';storage.save_project(workspace)
    real_fsync=storage.os.fsync
    def fail(fd):
        if stat.S_ISREG(storage.os.fstat(fd).st_mode):raise OSError(errno.ENOSPC,'Disk full')
        return real_fsync(fd)
    monkeypatch.setattr(storage.os,'fsync',fail)
    with pytest.raises(OSError):api.bind_project_path(workspace.id,str(target))
    assert target.read_bytes()==old
    assert api._project_paths_file.read_bytes()==registry
    assert not list(target.parent.glob('.*.tmp'))


def test_failed_first_bind_creates_no_binding(workspace,tmp_path,monkeypatch):
    api=launcher.NativeApi()
    def fail(*a):raise PermissionError('Read-only destination')
    monkeypatch.setattr(api,'_write_bound_project',fail)
    with pytest.raises(PermissionError):api.bind_project_path(workspace.id,str(tmp_path/'denied.maeprojz'))
    assert workspace.id not in api.project_paths
    assert not api._project_paths_file.exists()


def test_registry_failure_rolls_back_in_memory_binding(workspace,tmp_path,monkeypatch):
    api=launcher.NativeApi();old=tmp_path/'old.maeprojz';new=tmp_path/'new.maeprojz'
    api.bind_project_path(workspace.id,str(old));registry=api._project_paths_file.read_bytes()
    def fail():raise PermissionError('Registry write denied')
    monkeypatch.setattr(api,'_persist_project_paths',fail)
    with pytest.raises(PermissionError):api.bind_project_path(workspace.id,str(new))
    assert api.project_paths[workspace.id]==old
    assert api._project_paths_file.read_bytes()==registry
    assert new.is_file() and zipfile.is_zipfile(new)


def test_http_create_bind_and_load_native_project(workspace,tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    monkeypatch.setenv('MTA_ALLOW_INSECURE_NO_AUTH','true')
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',True)
    client=TestClient(main.app,headers={'X-MTA-Request':'1'})
    created=client.post('/api/projects',params={'title':'Nuovo caffè','target':'DAW','sample_rate':48000})
    assert created.status_code==200,created.text
    pid=created.json()['id'];api=launcher.NativeApi()
    require_writable_fsync(monkeypatch)
    target=tmp_path/'Nuovo caffè.maeprojz'
    assert api.bind_project_path(pid,str(target))['ok']
    loaded=client.get('/api/projects/'+pid)
    assert loaded.status_code==200,loaded.text
    assert loaded.json()['title']=='Nuovo caffè' and loaded.json()['sample_rate']==48000
    assert launcher.NativeApi().open_recent_project(pid)['ok']
    with zipfile.ZipFile(target) as z:assert json.loads(z.read('project/project.json'))['id']==pid


def test_configured_native_export_flushes_writable_output(workspace,tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    monkeypatch.setenv('MTA_ALLOW_INSECURE_NO_AUTH','true')
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',True)
    rendered=tmp_path/'rendered.wav';rendered.write_bytes(b'complete rendered audio')
    target=tmp_path/'saved.wav';target.write_bytes(b'previous audio')
    monkeypatch.setattr(main,'_render_configured_project_export',lambda *a:(rendered,'saved.wav','audio/wav','wav'))
    require_writable_fsync(monkeypatch)
    client=TestClient(main.app,headers={'X-MTA-Request':'1'})
    result=client.post(f'/api/projects/{workspace.id}/configured-export',json={'format':'wav','output_path':str(target)})
    assert result.status_code==200,result.text
    assert target.read_bytes()==rendered.read_bytes()


def test_metronome_render_flushes_writable_output(workspace,tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    monkeypatch.setenv('MTA_ALLOW_INSECURE_NO_AUTH','true')
    from app.models import Track,Clip
    import wave
    workspace.tracks=[Track(id='music',name='Music',filename='music.wav',duration_ms=2000,
                            sample_rate=48000,channels=1,clips=[Clip(id='musicclip',source_end_ms=2000)])]
    with wave.open(str(storage.audio_path(workspace.id,'music.wav')),'wb') as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(48000);out.writeframes(b'\x00\x00'*96000)
    workspace.bpm=120;workspace.metronome_bpm=120;storage.save_project(workspace)
    require_writable_fsync(monkeypatch)
    client=TestClient(main.app,headers={'X-MTA-Request':'1'})
    result=client.post(f'/api/projects/{workspace.id}/metronome-track',params={'mode':'fixed'})
    assert result.status_code==200,result.text
    track=result.json()['track']
    assert storage.audio_path(workspace.id,track['filename']).is_file()
