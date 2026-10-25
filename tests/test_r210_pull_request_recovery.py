"""Original API request survives authority/HTTP-parent loss without cache or inference."""
import io
import json
import zipfile

import pytest

from app import auth, ai_access, ai_request_dedup as dedup, ai_pull_coordinator as central, ai_pull_worker as worker
from test_r208_unified_adapter_billing_e2e import operator as operator, source_audio, ADAPTERS  # noqa: F401
from test_r210_pull_coordinator import authority as authority, economic, DirectClient, outcome  # noqa: F401
from test_r210_pull_lifecycle import api as api  # noqa: F401


def admitted(authority):
    key = 'persisted-pull-request-001'
    digest = dedup.fingerprint('whisper', b'{}', source_audio())
    dedup.admit(authority[0], key, digest)
    job = central.enqueue(authority[0], 'whisper', {}, source_wav=source_audio(), request_key=key, request_digest=digest)
    return key, job


def test_original_client_gets_durable_result_after_http_parent_was_lost(authority, api, monkeypatch):
    key, job = admitted(authority)
    token = ai_access.issue(authority[0], 'request recovery')['token']
    assert worker.run_once(DirectClient(authority[1]['credential']), authority[2] / 'recovery-node')
    assert dedup.request_status(authority[0], key)['state'] == 'completed'
    from app import ai_metering_agent
    monkeypatch.setattr(ai_metering_agent, 'execute_registered_worker', lambda *_a, **_kw: pytest.fail('Inference replayed'))
    headers = {'Authorization': 'Bearer ' + token}
    client = api[0]
    status = client.get('/api/ai-jobs/request-status/' + key, headers=headers)
    assert status.status_code == 200 and status.json()['job_id'] == job
    for _ in range(2):
        result = client.get('/api/ai-jobs/request-result/' + key, headers=headers)
        assert result.status_code == 200 and result.content == source_audio()
        assert result.headers['X-MTA-AI-Request-ID'] == key
    assert (authority[2] / 'execution-count').read_bytes() == b'1'
    repeat = client.post('/api/ai-jobs/execute-audio/whisper', content=source_audio(),
                         headers={**headers,'Content-Type':'audio/wav','X-MTA-AI-Idempotency-Key':key})
    assert repeat.status_code == 409 and repeat.json()['detail']['state'] == 'completed'


def test_cancel_original_request_reaches_worker_without_living_http_parent(authority, api):
    key, job = admitted(authority)
    credential = authority[1]['credential']
    grant = central.assignment(credential, 'a' * 32)
    dedup.cancel_admitted(authority[0], key)
    assert central.heartbeat(credential, job, grant['instance'], grant['nonce'])['cancelled']
    assert 'source_b64' not in central.assignment(credential, grant['instance'])
    central.complete(credential, job, grant['instance'], grant['nonce'], outcome())
    assert economic(job) == ('cancelled','finished','closed')
    assert dedup.request_status(authority[0], key)['state'] == 'cancelled'


def test_delivery_signature_is_frozen_across_key_rotation_and_revocation_blocks_replay(authority, api, monkeypatch):
    monkeypatch.setenv('MTA_AI_REMOTE_METERING_SIGNING_KEY_ID', 'first')
    monkeypatch.setenv('MTA_AI_REMOTE_METERING_WORKER_ID', 'trusted-authority')
    keys = {'first':'a'*64,'second':'b'*64}
    monkeypatch.setenv('MTA_AI_REMOTE_METERING_KEYS_JSON', json.dumps(keys))
    key, job = admitted(authority)
    assert worker.run_once(DirectClient(authority[1]['credential']), authority[2] / 'signed-node')
    token = ai_access.issue(authority[0], 'signed recovery')['token']
    headers = {'Authorization':'Bearer '+token}
    client = api[0]
    original = client.get('/api/ai-jobs/request-result/' + key, headers=headers)
    assert original.status_code == 200
    frozen = original.headers['X-MTA-AI-Metering-V2']
    monkeypatch.setenv('MTA_AI_REMOTE_METERING_SIGNING_KEY_ID', 'second')
    rotated = client.get('/api/ai-jobs/request-result/' + key, headers=headers)
    assert rotated.status_code == 200 and rotated.headers['X-MTA-AI-Metering-V2'] == frozen
    monkeypatch.setenv('MTA_AI_REMOTE_METERING_KEYS_JSON', json.dumps({'second':'b'*64}))
    assert client.get('/api/ai-jobs/request-result/' + key, headers=headers).status_code == 503
    assert economic(job) == ('done','finished','closed')


@pytest.mark.parametrize('kind', ADAPTERS)
def test_all_common_registered_artifact_adapters_cross_authority_storage(authority, kind, monkeypatch):
    # The inherited operator fixture emits real, bounded JSON/WAV ZIPs with
    # checksums. It does not load ML weights or claim semantic model acceptance.
    if kind == 'whisper':
        monkeypatch.setenv('MTA_AI_WORKER_WHISPER_EXECUTABLE', str(authority[2] / 'fixed_adapter.py'))
    node = central.register('artifact-node', [kind])
    job = central.enqueue(authority[0], kind, {}, source_wav=source_audio())
    assert worker.run_once(DirectClient(node['credential']), authority[2] / 'artifact-state')
    payload, meta = central.recover(job)
    assert meta['media_type'] == 'application/zip'
    with zipfile.ZipFile(io.BytesIO(payload)) as z:
        assert z.testzip() is None and 'manifest.json' in z.namelist()
    assert economic(job) == ('done','finished','closed')


def test_structured_score_is_staged_only_on_worker(authority, monkeypatch):
    from app.studio_score import Score
    from app.music_interchange import MusicResult, MusicPart
    from app.models import MidiNote
    score = Score(music=MusicResult(parts=[MusicPart(id='p',name='Singer',notes=[MidiNote(id='n',pitch=60,start_ms=0,duration_ms=500)])])).model_dump_json().encode()
    script = authority[2] / 'score_worker.py'
    script.write_text('''import argparse,json,pathlib,wave
p=argparse.ArgumentParser();p.add_argument('--request');p.add_argument('--output');a=p.parse_args()
r=json.loads(pathlib.Path(a.request).read_text());assert 'source_audio' not in r
assert json.loads(pathlib.Path(r['source_score']).read_text())['music']['parts'][0]['id']=='p'
with wave.open(a.output,'wb') as f:
 f.setnchannels(1);f.setsampwidth(2);f.setframerate(44100);f.writeframes(b'\\0\\0'*256)
''')
    script.chmod(0o700)
    monkeypatch.setenv('MTA_AI_WORKER_VOCAL_HARMONY_EXECUTABLE', str(script))
    node = central.register('score-node', ['vocal-harmony'])
    job = central.enqueue(authority[0], 'vocal-harmony', {}, source_json=score)
    assert worker.run_once(DirectClient(node['credential']), authority[2] / 'score-state')
    assert economic(job) == ('done','finished','closed')


@pytest.mark.parametrize('bad', ['../escape.json','output.manifest.json','bomb.json'])
def test_untrusted_result_archive_cannot_escape_or_expand_storage(bad, monkeypatch):
    payload = io.BytesIO()
    raw = b'{}' if bad != 'bomb.json' else b'x' * 1025
    monkeypatch.setattr(central,'MAX_BYTES',1024)
    with zipfile.ZipFile(payload,'w',compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(bad,raw)
        z.writestr('manifest.json',json.dumps({'version':1,'files':[{'name':bad,'type':'application/json'}]}))
    with pytest.raises(ValueError):
        central.validate_payload(payload.getvalue(),'application/zip')


@pytest.mark.parametrize('field,value', [('fingerprint','0'*64),('state','unknown')])
def test_corrupted_original_request_never_dispatches_and_blocks_readiness(authority, field, value):
    _, job = admitted(authority)
    with auth.db() as c:
        if field == 'fingerprint':
            c.execute('UPDATE ai_request_dedup SET fingerprint=?', (value,))
        else:
            c.execute('UPDATE ai_request_dedup SET state=?', (value,))
    with pytest.raises(central.FenceBlocked):
        central.assignment(authority[1]['credential'], 'a' * 32)
    with auth.db() as c:
        assert not central.inspect_state(c)['verified']
        assert c.execute('SELECT state FROM ai_pull_tasks WHERE job_id=?', (job,)).fetchone()[0] == 'queued'
