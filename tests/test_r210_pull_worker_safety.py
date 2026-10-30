"""Worker journal, privacy, cancelled admission and operator configuration safety."""
import json
from pathlib import Path

import pytest

from app import ai_pull_coordinator as central, ai_pull_worker as worker, auth
from test_r208_unified_adapter_billing_e2e import operator as operator  # noqa: F401
from test_r210_pull_coordinator import authority as authority, enqueue, economic, DirectClient  # noqa: F401


@pytest.mark.parametrize('phase', ['unknown','dispatched'])
def test_uncertain_phase_never_launches_or_claims(authority, phase):
    client = DirectClient(authority[1]['credential'])
    folder = authority[2] / 'uncertain'
    folder.mkdir(mode=0o700)
    journal = folder / 'active.json'
    journal.write_text(json.dumps({'phase': phase, 'binding': client.binding}))
    journal.chmod(0o600)
    client.call = lambda *_a, **_kw: pytest.fail('Uncertain state contacted authority or repeated execution')
    with pytest.raises(worker.WorkerUncertain):
        worker.run_once(client, folder)


@pytest.mark.parametrize('target', ['state','journal','config'])
def test_nonprivate_state_or_configuration_is_rejected(authority, target):
    client = DirectClient(authority[1]['credential'])
    folder = authority[2] / 'unsafe'
    folder.mkdir(mode=0o755 if target == 'state' else 0o700)
    if target == 'journal':
        journal = folder / 'active.json'
        journal.write_text(json.dumps({'phase': 'idle', 'binding': client.binding}))
        journal.chmod(0o644)
    if target == 'config':
        config = folder / 'config.json'
        config.write_text('{}')
        config.chmod(0o644)
        assert worker.main(['--config', str(config), '--state', str(folder / 'state')]) == 78
    else:
        with pytest.raises(ValueError, match='Private'):
            worker.run_once(client, folder)


def test_lost_completion_reply_retains_frozen_result_and_clears_after_exact_ack(authority):
    job = enqueue(authority)
    client = DirectClient(authority[1]['credential'])
    original = client.call
    def lost(action, body, **kwargs):
        result = original(action, body, **kwargs)
        if action == 'complete':
            raise OSError('Lost response after authority commit')
        return result
    client.call = lost
    folder = authority[2] / 'lost-complete'
    with pytest.raises(OSError):
        worker.run_once(client, folder)
    journal = json.loads((folder / 'active.json').read_text())
    assert journal['phase'] == 'ready' and 'source_b64' not in journal['task']
    assert economic(job) == ('done','finished','closed')
    client.call = original
    assert worker.run_once(client, folder)
    assert json.loads((folder / 'active.json').read_text()) == {'phase': 'done','binding': client.binding}
    assert (authority[2] / 'execution-count').read_bytes() == b'1'


def test_bad_success_ack_cannot_erase_frozen_result(authority):
    enqueue(authority)
    client = DirectClient(authority[1]['credential'])
    original = client.call
    def corrupt(action, body, **kwargs):
        result = original(action, body, **kwargs)
        return {'acknowledged': True, 'job_id': '0' * 32} if action == 'complete' else result
    client.call = corrupt
    folder = authority[2] / 'bad-ack'
    with pytest.raises(worker.WorkerUncertain):
        worker.run_once(client, folder)
    assert json.loads((folder / 'active.json').read_text())['phase'] == 'ready'


def test_policy_drift_on_node_fails_without_launch_or_fabricated_zero_cpu(authority, monkeypatch):
    job = enqueue(authority)
    from app import model_license_policy as rights
    original = rights.authorize_remote_execution
    def decision(kind, plan):
        result = original(kind, plan)
        from dataclasses import replace
        return replace(result, policy_sha256='0' * 64)
    class DifferentNodePolicy(DirectClient):
        def call(self, *args, **kwargs):
            # Isolate authority policy from the node's different local review.
            with monkeypatch.context() as context:
                context.setattr(rights, 'authorize_remote_execution', original)
                return super().call(*args, **kwargs)
    monkeypatch.setattr(rights, 'authorize_remote_execution', decision)
    assert worker.run_once(DifferentNodePolicy(authority[1]['credential']), authority[2] / 'drift')
    assert not (authority[2] / 'execution-count').exists()
    assert economic(job) == ('failed','finished','closed')
    assert central.recover(job)[1]['usage'] == {}


def test_completed_task_erasure_ack_clears_local_private_result_without_rerun(authority):
    job = enqueue(authority)
    client = DirectClient(authority[1]['credential'])
    original = client.call
    def lost(action, body, **kwargs):
        result = original(action, body, **kwargs)
        if action == 'complete':
            raise OSError('response lost')
        return result
    client.call = lost
    folder = authority[2] / 'erased-ack'
    with pytest.raises(OSError):
        worker.run_once(client, folder)
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE')
        central.record_erasure(c, authority[0])
        c.execute('DELETE FROM ai_pull_tasks WHERE job_id=?', (job,))
    client.call = original
    assert worker.run_once(client, folder)
    assert json.loads((folder / 'active.json').read_text()) == {'binding': client.binding,'phase': 'done'}
    assert (authority[2] / 'execution-count').read_bytes() == b'1'


@pytest.mark.parametrize('url', ['http://example.test','https://user:secret@example.test',
                                'https://example.test/other','https://example.test/?query=1'])
def test_worker_authority_url_cannot_select_untrusted_transport_or_paths(url):
    with pytest.raises(ValueError):
        worker.WorkerClient(url, 'a' * 32 + '.' + 'b' * 64)


def test_failed_payload_reports_known_cpu_without_publishing_invalid_media(authority):
    job = enqueue(authority)
    path = Path(authority[2]) / 'fixed_worker.py'
    path.write_text('import argparse\np=argparse.ArgumentParser();p.add_argument("--request");p.add_argument("--output");a=p.parse_args()\nopen(a.output,"wb").write(b"invalid wave")\n')
    assert worker.run_once(DirectClient(authority[1]['credential']), authority[2] / 'invalid-media')
    assert economic(job) == ('failed','finished','closed')
    assert set(central.recover(job)[1]['usage']) == {'cpu_seconds'}


def test_unverified_descendants_never_freeze_publish_or_release_assignment(authority, monkeypatch):
    from app import ai_metering_agent as agent
    job = enqueue(authority)
    monkeypatch.setattr(agent,'run_supervised_process',lambda *a,**kw:agent.Measurement(0,1,{'cpu_seconds':1},'worker',False))
    folder = authority[2] / 'unknown-descendants'
    with pytest.raises(worker.WorkerUncertain):
        worker.run_once(DirectClient(authority[1]['credential']),folder)
    assert json.loads((folder / 'active.json').read_text())['phase'] == 'dispatched'
    assert economic(job) == ('running','running','open')
