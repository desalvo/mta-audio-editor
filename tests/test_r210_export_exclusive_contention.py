"""Exclusive reader-blocking SQLite reproducer,not merely a reserved writer."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import subprocess
import threading
import time
import wave

from fastapi.testclient import TestClient
import pytest

from app import auth,regime_service_lease as lease
from app.sqlite_availability import BarrierUnavailable,is_busy
from test_r210_export_auth_contention import installed as installed,request_for  # noqa: F401


def test_exact_barrier_schema_read_fails_closed_under_exclusive_writer(installed):
    with sqlite3.connect(auth.db_path()) as writer:
        writer.execute('BEGIN EXCLUSIVE')
        with pytest.raises(BarrierUnavailable) as exc:lease.fence_held()
        assert exc.value.retryable and is_busy(exc.value.__cause__)
        writer.rollback()
    assert lease.fence_held() is False


def test_barrier_reuses_original_connection_without_committing_its_transaction(installed):
    from app.regime_admin_cutover import _initialize
    from app.regime_operation_fence import initialize
    with auth.db() as con:
        _initialize(con);initialize(con)
    with sqlite3.connect(auth.db_path()) as writer:
        writer.execute('BEGIN EXCLUSIVE')
        writer.execute('UPDATE regime_fence_state SET transitioning=1')
        assert lease.fence_held(writer) is True
        assert writer.in_transaction
        with pytest.raises(BarrierUnavailable):lease.fence_held()
        writer.rollback()
    assert lease.fence_held() is False


def test_barrier_timeout_is_bounded_restored_and_its_reader_is_released(installed):
    with closing(sqlite3.connect(auth.db_path())) as reader,sqlite3.connect(auth.db_path()) as writer:
        reader.execute('PRAGMA busy_timeout=1739')
        writer.execute('BEGIN EXCLUSIVE')
        began=time.monotonic()
        with pytest.raises(BarrierUnavailable):lease.fence_held(reader)
        assert time.monotonic()-began<1
        assert not reader.in_transaction
        assert reader.execute('PRAGMA busy_timeout').fetchone()[0]==1739
        writer.rollback()
        assert lease.fence_held(reader) is False
    # A failed accounting connection must release the OS service lease too.
    with sqlite3.connect(auth.db_path()) as writer:
        writer.execute('BEGIN EXCLUSIVE')
        with pytest.raises(BarrierUnavailable):
            with auth.db():pytest.fail('Locked database was admitted')
        writer.rollback()
    with lease.lease(exclusive=True):pass


@pytest.mark.parametrize('damage',['missing-row','missing-table'])
def test_missing_barrier_evidence_is_unavailable_and_never_retryable(installed,damage):
    from app import main
    from app.regime_admin_cutover import _initialize
    from app.regime_operation_fence import initialize
    request=request_for(installed)
    with auth.db() as con:
        _initialize(con);initialize(con)
        con.execute('DELETE FROM regime_fence_state' if damage=='missing-row' else 'DROP TABLE regime_fence_state')
    with closing(TestClient(main.app,raise_server_exceptions=False)) as client:
        client.cookies.set('mta_session',request.cookies['mta_session'])
        result=client.get('/api/projects')
        assert result.status_code==503,result.text
        assert result.json()['code']=='service_state_unavailable' and result.json()['retryable'] is False
        assert 'set-cookie' not in result.headers


@pytest.mark.parametrize('method',['POST','PUT','DELETE'])
def test_locked_mutations_are_not_advertised_as_replayable(installed,method):
    from app import main
    request=request_for(installed)
    with closing(TestClient(main.app,raise_server_exceptions=False)) as client:
        client.cookies.set('mta_session',request.cookies['mta_session'])
        with sqlite3.connect(auth.db_path()) as writer:
            writer.execute('BEGIN EXCLUSIVE')
            response=client.request(method,'/api/projects',headers={'X-MTA-Request':'1'},json={})
            assert response.status_code==503,response.text
            assert response.json()['code']=='database_busy' and response.json()['retryable'] is False
            writer.rollback()


def test_non_lock_operational_error_is_not_masked_as_transient(installed,monkeypatch):
    from app import main
    def broken(request):raise sqlite3.OperationalError('no such table: broken_programming_error')
    monkeypatch.setattr(main,'session_user',broken)
    with closing(TestClient(main.app,raise_server_exceptions=False)) as client:
        result=client.get('/api/projects')
        assert result.status_code==500
        assert 'database_busy' not in result.text


def test_locked_authentication_has_no_cached_positive_or_false_logout(installed):
    from app import main
    request=request_for(installed)
    # Match the existing installed-server fixture: do not start unrelated
    # application schedulers against this deliberately locked test database.
    with closing(TestClient(main.app,raise_server_exceptions=False)) as client:
        client.cookies.set('mta_session',request.cookies['mta_session'])
        initial=client.get('/api/projects')
        assert initial.status_code==200,initial.text
        with sqlite3.connect(auth.db_path()) as writer:
            writer.execute('BEGIN EXCLUSIVE');writer.execute('DELETE FROM sessions')
            for path in ['/api/session','/api/ai-execution/jobs?state=all&limit=100&offset=0','/api/projects']:
                response=client.get(path)
                assert response.status_code==503,response.text
                assert response.json()['code']=='database_busy' and response.json()['retryable'] is True
                assert response.headers['retry-after']=='1' and 'no-store' in response.headers['cache-control']
                assert 'set-cookie' not in response.headers
            writer.commit()
        assert client.get('/api/projects').status_code==401


@pytest.mark.parametrize('fmt',['mp3','wav','flac'])
@pytest.mark.parametrize('kind',['project','track'])
def test_original_export_survives_exclusive_lock_and_polls_download_after_release(installed,monkeypatch,fmt,kind):
    from app import main,storage
    from app.models import Track
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False)
    project=storage.create_project('Exclusive reader lock',owner_user_id=installed)
    source=storage.audio_path(project.id,'source.wav')
    with wave.open(str(source),'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(44100);f.writeframes(b'\0\0'*11025)
    project.tracks=[Track(id='track',name='Tone',filename='source.wav',duration_ms=250,sample_rate=44100,channels=1)]
    storage.save_project(project)
    entered=threading.Event();finish=threading.Event();calls=[]
    name='_configured_export_worker' if kind=='project' else '_track_export_worker'
    original=getattr(main,name)
    def controlled(*args,**kwargs):
        calls.append(args[0]);entered.set();assert finish.wait(8)
        return original(*args,**kwargs)
    monkeypatch.setattr(main,name,controlled)
    request=request_for(installed)
    with closing(TestClient(main.app,raise_server_exceptions=False)) as client:
        client.cookies.set('mta_session',request.cookies['mta_session'])
        url=f'/api/projects/{project.id}/configured-export-jobs' if kind=='project' else f'/api/projects/{project.id}/tracks/track/track-export-jobs'
        response=client.post(url,headers={'X-MTA-Request':'1'},json={'format':fmt})
        assert response.status_code==200,response.text
        job=response.json()['id'];assert entered.wait(3)
        try:
            with sqlite3.connect(auth.db_path()) as writer:
                writer.execute('BEGIN EXCLUSIVE')
                for path in ['/api/media-jobs/'+job,'/api/ai-execution/jobs?state=all&limit=100&offset=0']:
                    response=client.get(path)
                    assert response.status_code==503 and response.json()['code']=='database_busy',response.text
                writer.rollback()
        finally:finish.set()
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            response=client.get('/api/media-jobs/'+job);assert response.status_code==200,response.text
            state=response.json()
            if state['status'] in {'completed','failed'}:break
            time.sleep(.03)
        assert state['status']=='completed',state
        assert calls==[job]
        # Download also refuses a locked authentication read without corrupting
        # or regenerating the already completed output.
        with sqlite3.connect(auth.db_path()) as writer:
            writer.execute('BEGIN EXCLUSIVE')
            assert client.get(state['result']['download_url']).status_code==503
            writer.rollback()
        downloaded=client.get(state['result']['download_url'])
        assert downloaded.status_code==200 and len(downloaded.content)>100
        file=auth.data_root()/('exclusive-output-'+kind+'.'+fmt);file.write_bytes(downloaded.content)
        result=subprocess.run(['ffprobe','-v','error','-show_entries','stream=codec_name','-of','json',str(file)],
            check=True,capture_output=True,text=True,timeout=8)
        codec=json.loads(result.stdout)['streams'][0]['codec_name']
        assert codec.startswith('pcm_') if fmt=='wav' else codec==fmt


@pytest.mark.parametrize('text,expected',[('database is locked',True),('database table is locked: users',True),
    ('no such table: users',False),('syntax error',False),('database disk image is malformed',False)])
def test_only_actual_sqlite_lock_errors_are_retryable(text,expected):
    assert is_busy(sqlite3.OperationalError(text)) is expected


def test_production_browser_read_retry_never_replays_mutations_and_keeps_original_poll():
    source=Path(__file__).with_name('export_sqlite_busy.cjs')
    result=subprocess.run(['node',str(source)],check=False,capture_output=True,text=True,timeout=12)
    assert result.returncode==0,result.stdout+result.stderr
