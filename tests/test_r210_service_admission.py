"""Whole-service durable admission/drain through actual HTTP/process boundaries."""
import asyncio
from contextlib import closing
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import threading
import time

from fastapi import FastAPI, WebSocket
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient
import pytest

from app import auth, service_admission as gate, storage
from app.regime_operation_fence import FenceBlocked
from app.regime_service_lease import ServiceLeaseMiddleware
from app.service_admission_routes import router
from test_r210_queue_identity_stem_metering import env as env  # noqa: F401


@pytest.fixture
def authority(env,tmp_path,monkeypatch):
    monkeypatch.setenv('MTA_SERVICE_ADMISSION',gate.MODE)
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER','false')
    monkeypatch.setattr(storage,'ROOT',tmp_path/'projects');storage.ROOT.mkdir()
    with gate.operation('provision'): pass
    return env,tmp_path


def change(authority,*,generation=0,draining=True,identifier='drain-original'):
    return gate.change(actor=authority[0],expected_generation=generation,draining=draining,
        identifier=identifier,confirm=True)


def status(authority): return gate.inspect(actor=authority[0])


def test_full_drain_blocks_new_work_and_explicit_resume_preserves_generation(authority):
    stopped=change(authority)
    assert stopped['drained'] and stopped['generation']==1 and not stopped['transition_authorized']
    with pytest.raises(FenceBlocked):
        with gate.operation('new-work'): pytest.fail('New work admitted')
    with pytest.raises(FenceBlocked):
        with auth.db(): pytest.fail('Direct accounting connection admitted')
    assert change(authority,generation=1,draining=False)['phase']=='open'
    with gate.operation('new-work'): pass
    assert status(authority)['generation']==2


def test_predrain_request_can_finish_nested_original_background_work(authority):
    started=threading.Event();finish=threading.Event();done=[]
    with gate.operation('accepted-request'):
        assert not change(authority)['drained']
        def work():
            started.set();assert finish.wait(4)
            with auth.db() as c:assert c.execute('SELECT COUNT(*) FROM users').fetchone()[0]
            done.append(True)
        thread=gate.worker_thread(target=work,name='accepted-child');thread.start()
    assert started.wait(3)
    snapshot=status(authority)
    assert not snapshot['drained'] and snapshot['active_count']==1
    finish.set();thread.join(5);assert not thread.is_alive() and done==[True]
    assert status(authority)['drained']


def test_sleeping_periodic_cycle_cannot_mutate_after_barrier(authority):
    change(authority);called=[]
    assert gate.periodic('scheduler',lambda:called.append(True)) is None
    assert not called and status(authority)['drained']


def test_unexpected_exception_leaves_original_uncertain_admission(authority):
    with pytest.raises(RuntimeError):
        with gate.operation('uncertain-worker'):raise RuntimeError('Unverified external state')
    assert change(authority)['active_by_source']=={'uncertain-worker':1}
    assert not status(authority)['drained']


@pytest.mark.parametrize('field,value',[('expected_generation',True),('expected_generation',-1),
    ('draining',1),('confirm',False),('identifier','../foreign')])
def test_drain_confirmation_types_are_not_coerced(authority,field,value):
    body={'actor':authority[0],'expected_generation':0,'draining':True,
          'identifier':'drain-original','confirm':True};body[field]=value
    with pytest.raises(ValueError):gate.change(**body)
    assert status(authority)['phase']=='open'


def test_stale_replay_foreign_actor_and_audit_immutability(authority):
    first=change(authority)
    assert change(authority)==first
    with pytest.raises(FenceBlocked):change(authority,generation=0,identifier='another-drain')
    with gate.control(),auth.db() as c:
        c.execute("INSERT INTO users(username,email,password_hash,role,active,email_confirmed,created_at,updated_at) VALUES('reader','reader@example.test','unused','user',1,1,1,1)")
        other=c.execute("SELECT id FROM users WHERE username='reader'").fetchone()[0]
    with pytest.raises(FenceBlocked):gate.inspect(actor=other)
    with closing(sqlite3.connect(gate.path())) as c:
        with pytest.raises(sqlite3.IntegrityError):c.execute("DELETE FROM events")
        with pytest.raises(sqlite3.IntegrityError):c.execute("UPDATE admissions SET source='forged'")


@pytest.mark.parametrize('damage',['missing-journal','missing-instance','foreign-instance','unknown-build','corrupt'])
def test_missing_or_foreign_journal_never_reopens_admission(authority,monkeypatch,damage):
    change(authority);file=gate.path();seal=file.with_suffix('.instance')
    monkeypatch.setenv('MTA_SERVICE_ADMISSION','off')
    if damage=='missing-journal':file.unlink()
    elif damage=='missing-instance':seal.unlink()
    elif damage=='foreign-instance':seal.write_text('f'*64)
    elif damage=='unknown-build':
        with sqlite3.connect(file) as c:c.execute("UPDATE state SET build='foreign'")
    else:file.write_bytes(b'not SQLite')
    with pytest.raises((FenceBlocked,sqlite3.Error)):
        with gate.operation('new-work'):pytest.fail('Damaged barrier was bypassed')


def test_mode_removal_cannot_release_durable_barrier(authority,monkeypatch):
    change(authority);monkeypatch.setenv('MTA_SERVICE_ADMISSION','off')
    assert gate.active()
    with pytest.raises(FenceBlocked):gate.reserve('new-work')
    assert status(authority)['drained']


def web_app():
    app=FastAPI();app.include_router(router)
    app.add_middleware(ServiceLeaseMiddleware)
    app.add_middleware(gate.ServiceAdmissionMiddleware)
    @app.post('/work')
    def work():return {'ok':True}
    @app.get('/stream')
    async def stream():
        async def frames():
            yield b'first';await asyncio.sleep(.05);yield b'last'
        return StreamingResponse(frames())
    @app.websocket('/socket')
    async def socket(ws:WebSocket):
        await ws.accept()
        from starlette.websockets import WebSocketDisconnect
        try:
            while True:await ws.receive_text()
        except WebSocketDisconnect:pass
    return app


def test_actual_admin_api_auth_csrf_private_read_and_generation(authority):
    from test_r210_legal_documents import cookie
    with TestClient(web_app()) as client:
        assert client.get('/api/admin/service-admission').status_code==401
        client.cookies.update(cookie(authority[0]))
        body={'expected_generation':0,'draining':True,'identifier':'drain-web','confirm':True}
        assert client.post('/api/admin/service-admission/change',json=body).status_code==403
        response=client.post('/api/admin/service-admission/change',headers={'X-MTA-Request':'1'},json=body)
        assert response.status_code==200,response.text
        assert response.json()['drained'] and response.headers['cache-control']=='private, no-store'
        assert client.post('/work').status_code==503
        response=client.get('/api/admin/service-admission')
        assert response.status_code==200 and response.json()['drained']
        body.update(expected_generation=1,draining=False)
        assert client.post('/api/admin/service-admission/change',headers={'X-MTA-Request':'1'},json=body).status_code==200
        assert client.post('/work').status_code==200


def test_websocket_lifetime_is_counted_and_new_connection_refused(authority):
    from starlette.websockets import WebSocketDisconnect
    with TestClient(web_app()) as client:
        with client.websocket_connect('/socket'):
            assert change(authority)['active_by_source']=={'websocket':1}
        assert status(authority)['drained']
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect('/socket'):pytest.fail('New websocket admitted')
        assert exc.value.code==1013


def test_streaming_and_background_response_keep_admission_until_finished(authority):
    from starlette.background import BackgroundTask
    app=web_app();started=threading.Event();finish=threading.Event()
    @app.get('/background')
    def background():
        from fastapi.responses import Response
        def wait():started.set();assert finish.wait(5)
        return Response('ok',background=BackgroundTask(wait))
    errors=[]
    with TestClient(app) as client:
        def request():
            try:assert client.get('/background').status_code==200
            except BaseException as exc:errors.append(exc)
        t=threading.Thread(target=request);t.start();assert started.wait(3)
        assert not change(authority)['drained']
        finish.set();t.join(6);assert not errors and not t.is_alive()
        assert status(authority)['drained']


def test_actual_supervisor_sigkill_never_expires_original_work(authority):
    marker=authority[1]/'child-started'
    code='''import os,time
from pathlib import Path
from app import service_admission as a
with a.operation('independent-process'):
 Path(os.environ['MTA_DRAIN_MARKER']).touch()
 while True:time.sleep(.02)
'''
    env={**os.environ,'MTA_DATA_DIR':str(auth.data_root()),'MTA_DRAIN_MARKER':str(marker),
         'PYTHONPATH':str(Path(__file__).resolve().parents[1])}
    proc=subprocess.Popen([sys.executable,'-c',code],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        deadline=time.monotonic()+5
        while not marker.exists() and time.monotonic()<deadline:
            if proc.poll() is not None:raise AssertionError(proc.communicate()[1].decode())
            time.sleep(.01)
        assert marker.exists()
        assert not change(authority)['drained']
        os.kill(proc.pid,signal.SIGKILL);proc.wait(5)
        assert status(authority)['active_by_source']=={'independent-process':1}
        assert not status(authority)['drained']
    finally:
        if proc.poll() is None:proc.kill();proc.wait(5)


def test_pending_ledger_queue_and_original_file_receipts_block_ready(authority):
    with gate.control(),auth.db() as c:
        from app.regime_operation_fence import initialize,admit
        c.execute('BEGIN IMMEDIATE');initialize(c);admit(c,'original-checkout','checkout')
    folder=storage.ROOT/'project';folder.mkdir();(folder/'.ordinary-upload-pending.json').write_text('{}')
    result=change(authority)
    assert not result['drained'] and result['pending']['by_kind']['fenced_operations']==1
    assert result['pending']['by_kind']['file_publications']==1


@pytest.mark.parametrize('path_',['/api/admin/service-admissionevil','/api/pull-worker/foreign/complete',
    '/api/pull-worker/'+'f'*32+'/dispatch','/api/billing/credits/stripe-webhook/evil',
    '/api/projects/p/audio-capture/'+'a'*32+'/pcm'])
def test_lookalike_continuation_paths_cannot_create_work(authority,path_):
    change(authority)
    with TestClient(web_app()) as client:
        assert client.post(path_).status_code==503
