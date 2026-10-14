import os
from pathlib import Path
from types import SimpleNamespace
import pytest
from app import ai_durable_remote_executor as remote


def test_opt_in_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv('MTA_AI_DURABLE_REMOTE_URL', raising=False)
    assert remote.configured_remote() is None


@pytest.mark.parametrize('missing', ['MTA_AI_DURABLE_REMOTE_WORKER_ID', 'MTA_AI_DURABLE_REMOTE_TOKEN'])
def test_remote_requires_operator_identity(monkeypatch, missing):
    for key, value in [('MTA_AI_DURABLE_REMOTE_URL','https://example.com'),('MTA_AI_DURABLE_REMOTE_WORKER_ID','worker'),('MTA_AI_DURABLE_REMOTE_TOKEN','secret')]:
        monkeypatch.setenv(key, value)
    monkeypatch.delenv(missing)
    with pytest.raises(ValueError, match='worker identity and token'):
        remote.configured_remote()


@pytest.mark.parametrize('mode,plan', [
    ('track', {'input_source':'track'}),
    ('master', {'input_source':'master', 'input_track_id':'x'}),
    ('legacy_tracks', {'input_source':'legacy_tracks','track_ids':['a','b']}),
    ('unsupported', {'input_source':'other'}),
])
def test_unsupported_or_ambiguous_sources_fail_before_remote(mode, plan, tmp_path):
    project=SimpleNamespace(id='p', tracks=[SimpleNamespace(id='a',filename='a.wav'),SimpleNamespace(id='b',filename='b.wav')])
    with pytest.raises(ValueError):
        remote.render_source(plan,project,lambda *_: tmp_path/'a.wav',tmp_path/'result.wav')


def test_remote_execution_requires_valid_result_before_return(monkeypatch,tmp_path):
    from app import ai_metering_bridge,ai_worker_protocol
    monkeypatch.setenv('MTA_AI_DURABLE_REMOTE_URL','https://example.com')
    monkeypatch.setenv('MTA_AI_DURABLE_REMOTE_WORKER_ID','worker')
    monkeypatch.setenv('MTA_AI_DURABLE_REMOTE_TOKEN','secret')
    monkeypatch.setattr(remote,'render_source',lambda *args: (args[3].write_bytes(b'input'), {'bytes':5})[1])
    monkeypatch.setattr(ai_worker_protocol,'verify_preview_wav',lambda path: {'bytes':path.stat().st_size})
    events=[]
    def fake_settle(job_id, **kw):
        events.append((job_id,kw['worker_id'],kw['wav']))
        return b'audio', 'audio/wav','remote-job'
    monkeypatch.setattr(ai_metering_bridge,'infer_and_register_remote_settlement',fake_settle)
    result, info=remote.execute('local-job',{'input_source':'master'},SimpleNamespace(id='p'),lambda *_: tmp_path/'track.wav')
    assert result==b'audio'
    assert info['remote_job_id']=='remote-job'
    assert events[0][:2]==('local-job','worker')


def test_remote_cancelled_before_submitting(monkeypatch):
    from threading import Event
    monkeypatch.setenv('MTA_AI_DURABLE_REMOTE_URL','https://example.com')
    monkeypatch.setenv('MTA_AI_DURABLE_REMOTE_WORKER_ID','worker')
    monkeypatch.setenv('MTA_AI_DURABLE_REMOTE_TOKEN','secret')
    event=Event();event.set()
    with pytest.raises(RuntimeError,match='cancelled'):
        remote.execute('j',{},None,None,cancel_event=event)
