"""Actual subprocess -> packaged artifact -> real CPU billing ledger, per adapter."""
import io
import json

import wave
import zipfile


import pytest
from app import ai_billing, ai_metering_agent
from app.auth import db, init_auth_db

ADAPTERS = ('whisper', 'chords-ml', 'demucs', 'drumsep', 'sam-audio',
            'singer-separation', 'backing-vocals')


def source_audio():
    output = io.BytesIO()
    with wave.open(output, 'wb') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(44100)
        f.writeframes(b'\0\0' * 256)
    return output.getvalue()


@pytest.fixture
def operator(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR', str(tmp_path / 'private'))
    monkeypatch.delenv('MTA_AI_CGROUP_PARENT', raising=False)
    monkeypatch.setenv('MTA_AI_WORKER_ENABLED', 'true')
    init_auth_db()
    with db() as con:
        con.execute("INSERT INTO users(username,email,password_hash,active,role,created_at,updated_at) VALUES('worker_account','account@example.org','fake',1,'user',1,1)")
        uid = con.execute("SELECT id FROM users WHERE username='worker_account'").fetchone()[0]
    ai_billing.set_user_billing_enabled(uid, True)
    ai_billing.set_price('cpu_seconds', 1000000, valid_from='2025-01-01')
    worker = tmp_path / 'fixed_adapter.py'
    worker.write_text('''#!/usr/bin/env python3
import argparse, json, wave, pathlib, hashlib
p=argparse.ArgumentParser(); p.add_argument('--request'); p.add_argument('--output'); a=p.parse_args()
request=json.loads(pathlib.Path(a.request).read_text()); source=pathlib.Path(request['source_audio'])
assert source.is_file() and source.name=='source.wav'
folder=pathlib.Path(a.output).parent
if request['kind'] in ('whisper','chords-ml'):
    target=folder/'result.json'; data=json.dumps({'kind':request['kind'],'items':[]}).encode(); target.write_bytes(data); media='application/json'
else:
    target=folder/'result.wav'
    with wave.open(str(target),'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(44100);f.writeframes(b'\\0\\0'*256)
    data=target.read_bytes();media='audio/wav'
(folder/'output.manifest.json').write_text(json.dumps({'version':1,'files':[{'name':target.name,'type':media,'sha256':hashlib.sha256(data).hexdigest()}]}))
''', encoding='utf-8')
    worker.chmod(0o700)
    for kind in ADAPTERS:
        env_name='MTA_AI_WORKER_'+kind.upper().replace('-','_')+'_EXECUTABLE'
        monkeypatch.setenv(env_name, str(worker))
    return uid


@pytest.mark.parametrize('kind', ADAPTERS)
def test_each_real_adapter_job_is_metered_billed_and_packaged(operator, kind):
    payload, metadata = ai_metering_agent.execute_registered_worker(
        operator, kind, {'kind': kind}, source_wav=source_audio())
    assert metadata['media_type']=='application/zip'
    assert metadata['job_id']
    assert metadata['usage']['cpu_seconds'] >= 0
    assert not metadata['gpu_metered']
    with zipfile.ZipFile(io.BytesIO(payload)) as z:
        assert 'manifest.json' in z.namelist()
        assert any(name.endswith('.wav' if kind not in ('whisper','chords-ml') else '.json') for name in z.namelist())
    with db() as con:
        row=con.execute('SELECT kind,status,resource_source,usage_json FROM ai_compute_jobs WHERE id=?', (metadata['job_id'],)).fetchone()
    assert row['kind']==kind and row['status']=='done'
    assert row['resource_source'] in ('worker','cgroup')
    usage=json.loads(row['usage_json'])
    assert usage['cpu_seconds']==metadata['usage']['cpu_seconds']
    assert not any(key.startswith('gpu_') for key in usage)


def test_cancellation_during_artifact_packaging_cannot_bill_success(operator, monkeypatch):
    from app import ai_worker_artifacts
    original=ai_worker_artifacts.package_artifacts
    cancelled=[False]
    def finish_packaging(path):
        result=original(path)
        cancelled[0]=True
        return result
    monkeypatch.setattr(ai_worker_artifacts,'package_artifacts',finish_packaging)
    with pytest.raises(RuntimeError, match='cancelled during artifact packaging'):
        ai_metering_agent.execute_registered_worker(
            operator, 'whisper', {'kind':'whisper'}, source_wav=source_audio(),
            cancel_check=lambda: cancelled[0])
    with db() as con:
        rows=con.execute("SELECT status FROM ai_compute_jobs WHERE kind='whisper'").fetchall()
    assert len(rows)==1 and rows[0]['status']=='failed'
