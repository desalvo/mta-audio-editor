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
    # These fixture adapters use no external checkpoint; explicitly authorize
    # their synthetic test artifacts without weakening the production default.
    from app.model_license_policy import configure
    for model in ('audio-separator-weights','drumsep-weights'):
        configure(model,{'mode':'cost_recovery','acknowledge_responsibility':True,
            'evidence_url':'https://example.org/fixture-license','reason':'Generated test audio without third-party weights',
            'free_access_confirmed':False,'authorization_basis':'written_permission','confirm_risk_twice':True},uid)
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


def test_free_only_real_worker_bypasses_paid_admission_without_losing_accounting(operator,monkeypatch):
    from app.model_license_policy import configure
    configure('whisper',{'mode':'free_only','acknowledge_responsibility':True,
        'evidence_url':'https://example.org/fixture-license','reason':'Free fixture inference with no subscription or storage charge',
        'free_access_confirmed':True},operator)
    from app import resource_access
    def paid_gate(uid):raise AssertionError('A free-only worker reached the paid gate')
    monkeypatch.setattr(resource_access,'preflight',paid_gate)
    payload,metadata=ai_metering_agent.execute_registered_worker(operator,'whisper',{'kind':'whisper'},source_wav=source_audio())
    assert payload and metadata['billable'] is False and metadata['usage']['cpu_seconds']>0
    with db() as con:
        row=con.execute('SELECT billable FROM ai_compute_jobs WHERE id=?',(metadata['job_id'],)).fetchone()
        assert row['billable']==0
        if con.execute("SELECT 1 FROM sqlite_master WHERE name='resource_job_contracts'").fetchone():
            assert not con.execute('SELECT 1 FROM resource_job_contracts WHERE job_id=?',(metadata['job_id'],)).fetchone()
    report=ai_billing.report(user_id=operator)
    assert report['total_micro']==0 and report['license_exempt_jobs']==1 and report['diagnostic_jobs']==0


def test_cancellation_during_artifact_packaging_cannot_bill_success(operator, monkeypatch):
    from app import ai_worker_artifacts
    original=ai_worker_artifacts.package_artifacts
    cancelled=[False]
    def finish_packaging(path, **kwargs):
        result=original(path, **kwargs)
        cancelled[0]=True
        return result
    monkeypatch.setattr(ai_worker_artifacts,'package_artifacts',finish_packaging)
    with pytest.raises(RuntimeError, match='cancelled during artifact packaging'):
        ai_metering_agent.execute_registered_worker(
            operator, 'whisper', {'kind':'whisper'}, source_wav=source_audio(),
            cancel_check=lambda: cancelled[0])
    with db() as con:
        rows=con.execute("SELECT status FROM ai_compute_jobs WHERE kind='whisper'").fetchall()
    assert len(rows)==1 and rows[0]['status']=='cancelled'


def test_admin_artifact_policy_is_frozen_and_not_overridden_by_plan(operator, monkeypatch, tmp_path):
    from app import ai_arranger_runtime as queue, ai_worker_artifacts
    monkeypatch.setattr(queue, '_ROOT', tmp_path / 'queue')
    queue.configure_execution_settings({'max_artifact_mib': 2048})
    monkeypatch.setenv('MTA_AI_JOB_MAX_ARTIFACT_MIB', '8192')
    runner = ai_metering_agent.run_metered_process
    packager = ai_worker_artifacts.package_artifacts
    def run(*args, **kwargs):
        assert kwargs['env']['MTA_AI_JOB_MAX_ARTIFACT_MIB'] == '2048'
        result = runner(*args, **kwargs)
        queue.configure_execution_settings({'max_artifact_mib': 64})
        return result
    def package(path, **kwargs):
        assert kwargs['max_bytes'] == 2 * 1024**3
        return packager(path, **kwargs)
    monkeypatch.setattr(ai_metering_agent, 'run_metered_process', run)
    monkeypatch.setattr(ai_worker_artifacts, 'package_artifacts', package)
    payload, _ = ai_metering_agent.execute_registered_worker(operator, 'whisper',
        {'kind': 'whisper', 'max_artifact_mib': 8192}, source_wav=source_audio())
    assert payload and queue.artifact_limit_mib() == 64
