"""Full-length multi-stem results cross every delivery limit without bypasses."""
import hashlib
import io
import json
from pathlib import Path
import wave
from types import SimpleNamespace

import pytest

from app import ai_payload_limits as limits, ai_worker_artifacts as artifacts
from app.ai_unified_adapter import _artifacts
from test_r210_queue_identity_stem_metering import env as env  # noqa: F401


def test_six_stems_over_old_limits_roundtrip_server_cache_and_native(tmp_path, monkeypatch,env):
    from app import ai_result_cache as cache, ai_remote_client as client
    from app import ai_server_execution as server, native_ai_routing as native
    from app.ai_billing_routes import _verified_worker_response
    # 70 seconds x six real PCM WAVs >64 MiB. Noise avoids hiding a 32 MiB
    # delivery bug behind a tiny compressed ZIP of silence; no ML/GPU required.
    chunk = hashlib.shake_256(b'MTA r210 PCM fixture').digest(65536)
    entries = []
    for index in range(6):
        path = tmp_path / f'stem_{index}.wav'
        with wave.open(str(path), 'wb') as stream:
            stream.setnchannels(2); stream.setsampwidth(2); stream.setframerate(44100)
            remaining = 70 * 44100 * 2 * 2
            while remaining:
                block = chunk[:min(remaining, len(chunk))]
                stream.writeframesraw(block); remaining -= len(block)
        entries.append((path, 'audio/wav'))
    assert sum(p.stat().st_size for p, _ in entries) > 64 * 1024 * 1024
    _artifacts(tmp_path, entries)
    payload, mime = artifacts.package_artifacts(tmp_path)
    assert len(payload) > 64 * 1024 * 1024
    meta = {'job_id': 'job-full-stems', 'media_type': mime}
    assert _verified_worker_response(payload, meta) == ('job-full-stems', mime)
    monkeypatch.setenv('MTA_AI_RESULT_CACHE_DIR', str(tmp_path / 'cache'))
    key = 'full-stem-request-123456'
    assert cache.save(1, key, payload, mime, meta['job_id'])
    assert cache.load(1, key, meta['job_id']) == (payload, mime)
    response = io.BytesIO(payload)
    response.headers = {'Content-Type': mime, 'Content-Length': str(len(payload)),
        'X-MTA-AI-Job-ID': meta['job_id'], 'X-MTA-AI-Request-ID': key,
        'X-MTA-AI-Result-SHA256': hashlib.sha256(payload).hexdigest()}
    verified = client._read_verified_result(response, expected_request_id=key, require_attestation=True)
    assert verified == (payload, mime, meta['job_id'])
    # Exercise web result unpacking as well as native remote consumption.
    from app import ai_metering_agent as agent,ai_global_execution as execution
    monkeypatch.setattr('app.ai_metering_agent.execute_registered_worker', lambda *a, **kw: (payload, meta))
    def convert(args, **kw):
        assert not kw['cancel_check']()
        Path(args[-1]).write_bytes(b'input fixture')
        return agent.Measurement(0,0,{},'unmetered',False)
    monkeypatch.setattr(agent, 'run_metered_process', convert)
    result, job = execution.execute(env,'demucs',lambda _:server.infer('demucs', entries[0][0]))
    assert job == meta['job_id'] and len(result['audio']) == 6
    del result
    monkeypatch.setattr(native, '_read', lambda: {'workers': {'demucs': {
        'mode': 'remote', 'url': 'https://ai.example', 'token': 'fixture-token'}}})
    monkeypatch.setenv('MTA_NATIVE_REMOTE_JOURNAL', str(tmp_path / 'pending'))
    monkeypatch.setattr(client, 'infer_audio', lambda *a, **kw: verified)
    result, job = native.infer('demucs', entries[0][0])
    assert job == meta['job_id'] and set(result['audio']) == {p.name for p, _ in entries}
    assert not list((tmp_path / 'pending').glob('*.json'))


def test_shared_source_and_result_limits_agree():
    from app import ai_remote_client, ai_result_cache, ai_worker_protocol
    assert ai_remote_client.MAX_AUDIO_BYTES == ai_worker_protocol.MAX_SOURCE_BYTES == limits.MAX_SOURCE_BYTES
    assert artifacts.MAX_ARTIFACT_BYTES == limits.MAX_ARTIFACT_BYTES == 1024**3
    assert ai_remote_client.MAX_RESULT_BYTES == ai_result_cache.MAX_BYTES == artifacts.MAX_RESULT_BYTES
    assert limits.MAX_RESULT_BYTES > limits.MAX_ARTIFACT_BYTES


def test_sparse_oversize_stem_rejected_before_read_or_manifest(tmp_path):
    path = tmp_path / 'huge.wav'
    with path.open('wb') as stream:
        stream.truncate(limits.MAX_ARTIFACT_BYTES + 1)
    with pytest.raises(RuntimeError, match='artifact size limit'):
        _artifacts(tmp_path, [(path, 'audio/wav')])
    assert not (tmp_path / 'output.manifest.json').exists()


def test_zip_overhead_is_separate_from_uncompressed_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(artifacts, 'MAX_ARTIFACT_BYTES', 32)
    path = tmp_path / 'notes.txt'; path.write_bytes(bytes(range(32)))
    _artifacts(tmp_path, [(path, 'text/plain')])
    payload, mime = artifacts.package_artifacts(tmp_path)
    assert len(payload) > 32 and mime == 'application/zip'
    monkeypatch.setattr(artifacts, 'MAX_RESULT_BYTES', len(payload) - 1)
    with pytest.raises(ValueError, match='archive exceeds size limit'):
        artifacts.package_artifacts(tmp_path)


def test_cache_and_remote_still_reject_oversized_results(tmp_path, monkeypatch):
    from app import ai_result_cache as cache, ai_remote_client as client
    monkeypatch.setenv('MTA_AI_RESULT_CACHE_DIR', str(tmp_path))
    monkeypatch.setattr(cache, 'MAX_BYTES', 4)
    with pytest.raises(ValueError, match='Invalid cached'):
        cache.save(1, 'oversized-result-123', b'12345', 'audio/wav', 'job')
    monkeypatch.setattr(client, 'MAX_RESULT_BYTES', 4)
    response = SimpleNamespace(headers={'Content-Type': 'audio/wav', 'Content-Length': '5'})
    with pytest.raises(client.RemoteAIError, match='exceeds the size limit'):
        client._read_verified_result(response)


def test_server_manifest_is_not_charged_to_audio_budget(tmp_path, monkeypatch,env):
    import zipfile
    from app import ai_server_execution as server
    from app import ai_metering_agent as agent,ai_global_execution as execution
    monkeypatch.setattr(limits, 'MAX_ARTIFACT_BYTES', 4)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as z:
        z.writestr('stem.wav', b'RIFF'); z.writestr('manifest.json', json.dumps({'version': 1}))
    monkeypatch.setattr('app.ai_metering_agent.execute_registered_worker',
                        lambda *a, **kw: (buffer.getvalue(), {'job_id': 'job'}))
    def convert(args,**kw):
        assert not kw['cancel_check']()
        Path(args[-1]).write_bytes(b'fixture')
        return agent.Measurement(0,0,{},'unmetered',False)
    monkeypatch.setattr(agent,'run_metered_process',convert)
    result, job = execution.execute(env,'demucs',lambda _:server.infer('demucs', tmp_path / 'source.wav'))
    assert result['audio'] == {'stem.wav': b'RIFF'} and job == 'job'


def test_worker_size_failure_has_specific_safe_diagnostic():
    from app.ai_cgroup_metering import _worker_failure, safe_failure_metadata
    detail = safe_failure_metadata(_worker_failure('RuntimeError: Worker outputs exceed artifact size limit', 1))
    assert detail['category'] == 'worker_output_size_limit'
    assert detail['metering_valid'] is False


def test_native_upload_reads_beyond_old_32mib_limit(tmp_path, monkeypatch):
    from app import native_ai_routing as native, ai_remote_client as client
    path = tmp_path / 'source.wav'
    with path.open('wb') as stream:
        stream.write(b'RIFF'); stream.truncate(33 * 1024 * 1024)
    monkeypatch.setattr(native, '_read', lambda: {'workers': {'demucs': {
        'mode': 'remote', 'url': 'https://ai.example', 'token': 'fixture-token'}}})
    monkeypatch.setenv('MTA_NATIVE_REMOTE_JOURNAL', str(tmp_path / 'pending'))
    def infer(*args, **kw):
        assert len(args[3]) == path.stat().st_size
        return b'{"ok":true}', 'application/json', 'job'
    monkeypatch.setattr(client, 'infer_audio', infer)
    assert native.infer('demucs', path)[0]['json']['result.json'] == {'ok': True}


def test_oversize_source_rejected_before_job_or_billing(tmp_path, monkeypatch):
    from app import ai_metering_agent as agent, ai_worker_registry, ai_billing
    monkeypatch.setattr(ai_worker_registry, 'resolve_worker', lambda _: tmp_path / 'trusted.py')
    monkeypatch.setattr(limits, 'MAX_SOURCE_BYTES', 4)
    monkeypatch.setattr(ai_billing, 'create_job', lambda *a, **kw: pytest.fail('No billing job may be opened'))
    with pytest.raises(ValueError, match='source audio exceeds size limit'):
        agent.execute_registered_worker(1, 'demucs', {'kind': 'demucs'}, source_wav=b'12345')
