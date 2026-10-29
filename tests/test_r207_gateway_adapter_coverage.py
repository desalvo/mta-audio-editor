"""Exercise safe gateway and adapter branches without loading GPU models."""
import json
import sys
import types
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import ai_gateway, ai_unified_adapter as unified


@pytest.mark.parametrize('url,allowed', [
    ('http://127.0.0.1:8001', True), ('http://localhost:8001/', True),
    ('http://192.168.1.2:8001', True), ('https://example.org', True),
    ('http://8.8.8.8:8001', False), ('http://example.org', False),
    ('file:///tmp/a', False), ('http://user:password@127.0.0.1', False),
    ('https://example.org/api/admin', False), ('nonsense', False),
])
def test_gateway_upstream_validation(monkeypatch, url, allowed):
    monkeypatch.setenv('MTA_ACE_STEP_URL', url)
    if allowed:
        assert ai_gateway.upstream_url() == url.rstrip('/')
    else:
        with pytest.raises(RuntimeError):
            ai_gateway.upstream_url()


def test_gateway_authorization_methods_size_and_audit(monkeypatch):
    web = FastAPI()
    web.include_router(ai_gateway.router)
    calls = []
    monkeypatch.setattr(ai_gateway.ai_access, 'authenticate', lambda token: {'id': 5, 'user_id': 6} if token == 'valid' else None)
    monkeypatch.setattr(ai_gateway.ai_access, 'usage', lambda *args: calls.append(args))
    client = TestClient(web)
    assert client.get('/api/ai-gateway/health').status_code == 401
    headers = {'authorization': 'Bearer valid'}
    assert client.get('/api/ai-gateway/other', headers=headers).status_code == 404
    assert client.get('/api/ai-gateway/v1/generate', headers=headers).status_code == 405
    monkeypatch.setattr(ai_gateway, 'MAX_BODY', 1)
    assert client.post('/api/ai-gateway/v1/generate', headers=headers, content=b'xx').status_code == 413
    assert calls == []


def test_gateway_proxy_success_limits_and_errors(monkeypatch):
    web = FastAPI()
    web.include_router(ai_gateway.router)
    monkeypatch.setattr(ai_gateway.ai_access, 'authenticate', lambda _: {'id': 2, 'user_id': 3})
    calls = []
    monkeypatch.setattr(ai_gateway.ai_access, 'usage', lambda *args: calls.append(args))
    monkeypatch.setenv('MTA_ACE_STEP_URL', 'https://worker.example.org')
    monkeypatch.setenv('MTA_ACE_STEP_TOKEN', 'private-internal-token')
    captured = []
    mode = {'value': 'ok'}

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            assert kwargs['trust_env'] is False and kwargs['follow_redirects'] is False
        async def __aenter__(self):
            return self
        async def __aexit__(self, *_):
            return False
        async def request(self, method, url, **kwargs):
            captured.append((method, url, kwargs))
            if mode['value'] == 'runtime':
                raise RuntimeError('upstream gone')
            if mode['value'] == 'timeout':
                raise httpx.ConnectTimeout('no response')
            return httpx.Response(200, content=b'answer', headers={'content-type': 'audio/wav'})

    monkeypatch.setattr(httpx, 'AsyncClient', FakeAsyncClient)
    client = TestClient(web)
    headers = {'Authorization': 'Bearer valid', 'Content-Type': 'application/json'}
    ok = client.get('/api/ai-gateway/health?seed=3', headers=headers)
    assert ok.status_code == 200 and ok.content == b'answer'
    assert captured[-1][1] == 'https://worker.example.org/health'
    assert captured[-1][2]['headers']['authorization'] == 'Bearer private-internal-token'
    assert captured[-1][2]['params']['seed'] == '3'
    monkeypatch.setattr(ai_gateway, 'MAX_BODY', 3)
    assert client.get('/api/ai-gateway/health', headers=headers).status_code == 502
    monkeypatch.setattr(ai_gateway, 'MAX_BODY', 100)
    for error in ('runtime', 'timeout'):
        mode['value'] = error
        assert client.get('/api/ai-gateway/health', headers=headers).status_code == 502
    assert len(calls) == 4 and all(call[1] == 3 for call in calls)


def _staged(tmp_path):
    source = tmp_path / 'source.wav'
    source.write_bytes(b'stage')
    return str(source), tmp_path / 'preview.wav'


def test_unified_manifest_validation(tmp_path):
    file = tmp_path / 'a.json'
    file.write_text('{}')
    unified._artifacts(tmp_path, [(file, 'application/json')])
    assert json.loads((tmp_path/'output.manifest.json').read_text())['files'][0]['name'] == 'a.json'
    foreign = tmp_path/'foreign'
    foreign.mkdir()
    (foreign/'a.json').write_text('{}')
    with pytest.raises(RuntimeError):
        unified._artifacts(tmp_path, [(foreign/'a.json', 'application/json')])
    with pytest.raises(RuntimeError):
        unified._artifacts(tmp_path, [(tmp_path/'missing', 'application/json')])


def test_unified_transcripts_and_chords(tmp_path, monkeypatch):
    source, output = _staged(tmp_path)
    from app import music_text
    class Dummy:
        def model_dump(self, **kwargs):
            assert kwargs['mode'] == 'json'
            return {'text': 'test'}
    monkeypatch.setattr(music_text, 'extract_lyrics', lambda *args, **kwargs: [Dummy()])
    monkeypatch.setattr(music_text, 'extract_chords_progressive', lambda *args, **kwargs: [Dummy()])
    unified.infer({'kind': 'whisper', 'source_audio': source, 'language': 'it', 'advanced_alignment': True}, output)
    assert json.loads((tmp_path/'transcript.json').read_text())['lines'] == [{'text': 'test'}]
    unified.infer({'kind': 'chords-ml', 'source_audio': source}, output)
    assert json.loads((tmp_path/'chords.json').read_text())['chords'] == [{'text': 'test'}]


def test_unified_drumsep_and_missing_model(tmp_path, monkeypatch):
    from model_rights_fixtures import authorize_fixture
    authorize_fixture(monkeypatch,tmp_path,'drumsep-weights')
    source, output = _staged(tmp_path)
    monkeypatch.setenv('MTA_AI_DRUMSEP_MODEL', str(tmp_path/'missing.onnx'))
    with pytest.raises(RuntimeError, match='checkpoint'):
        unified.infer({'kind': 'drumsep', 'source_audio': source}, output)
    model = tmp_path/'model.onnx'
    model.write_bytes(b'model')
    monkeypatch.setenv('MTA_AI_DRUMSEP_MODEL', str(model))
    from app import drumsep_onnx_worker
    def fake_infer(source, model, folder):
        p = folder/'drums.wav'
        p.write_bytes(b'audio')
        return [p]
    monkeypatch.setattr(drumsep_onnx_worker, 'infer', fake_infer)
    unified.infer({'kind': 'drumsep', 'source_audio': source}, output)
    assert (tmp_path/'output.manifest.json').is_file()


def test_unified_subprocess_models(tmp_path, monkeypatch):
    source, output = _staged(tmp_path)
    import subprocess
    calls = []
    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if 'demucs.separate' in cmd:
            folder = tmp_path/'demucs'/'htdemucs'/'source'
            folder.mkdir(parents=True)
            (folder/'vocals.wav').write_bytes(b'a')
        else:
            Path(cmd[cmd.index('--output') + 1]).write_bytes(b'a')
    monkeypatch.setattr(subprocess, 'run', fake_run)
    with pytest.raises(ValueError, match='supported SAM checkpoint'):
        unified.infer({'kind': 'sam-audio', 'source_audio': source}, output)
    monkeypatch.setenv('MTA_AI_SAM_MODEL', 'sam-audio-small')
    unified.infer({'kind': 'sam-audio', 'source_audio': source}, output)
    with pytest.raises(ValueError, match='declared Demucs checkpoint'):
        unified.infer({'kind': 'demucs', 'source_audio': source, 'model': '../bad'}, output)
    unified.infer({'kind': 'demucs', 'source_audio': source}, output)
    assert (tmp_path/'stem_vocals.wav').exists()
    assert len(calls) == 2


@pytest.mark.parametrize('bad', [
    {'singers': []}, {'singers': [{}] * 2},
    {'singers': [{'id': 'wrong', 'start': 0, 'end': 1}] * 2},
    {'singers': [{'id': f'singer_{i}', 'start': 4, 'end': 1} for i in (1, 2)]},
    {'singers': [{'id': f'singer_{i}', 'start': 0, 'end': 2} for i in (1, 2)], 'selected': 'singer_3'},
    {'singers': [{'id': f'singer_{i}', 'start': 0, 'end': 2} for i in (1, 2)], 'model': '../bad'},
])
def test_singer_separation_invalid_options(tmp_path, bad):
    source, output = _staged(tmp_path)
    with pytest.raises(ValueError):
        unified.infer({'kind': 'singer-separation', 'source_audio': source, **bad}, output)


def test_singer_separation_selected_and_all(tmp_path, monkeypatch):
    source, output = _staged(tmp_path)
    import subprocess
    calls = []
    def fake_run(args, **kwargs):
        calls.append(args)
        Path(args[args.index('--output') + 1]).write_bytes(b'a')
    monkeypatch.setattr(subprocess, 'run', fake_run)
    singers = [{'id': f'singer_{i}', 'start': i, 'end': i + 1} for i in (1, 2)]
    unified.infer({'kind': 'singer-separation', 'source_audio': source, 'singers': singers, 'selected': 'singer_2'}, output)
    assert (tmp_path/'singer_2.wav').exists() and len(calls) == 1
    unified.infer({'kind': 'singer-separation', 'source_audio': source, 'singers': singers, 'selected': 'all'}, output)
    assert len(calls) == 3


def test_backing_vocals_artifact_security(tmp_path, monkeypatch):
    # Select the operator-filename branch; the default is now Mega53.
    monkeypatch.setattr('app.model_license_policy.effective_backing_model',lambda plan:'')
    from model_rights_fixtures import authorize_fixture
    authorize_fixture(monkeypatch,tmp_path,'audio-separator-weights')
    source, output = _staged(tmp_path)
    class Separator:
        outputs = []
        def __init__(self, **kwargs):
            pass
        def load_model(self, **kwargs):
            pass
        def separate(self, source):
            return self.outputs
    package = types.ModuleType('audio_separator')
    sub = types.ModuleType('audio_separator.separator')
    sub.Separator = Separator
    monkeypatch.setitem(sys.modules, 'audio_separator', package)
    monkeypatch.setitem(sys.modules, 'audio_separator.separator', sub)
    monkeypatch.setitem(sys.modules, 'torch', types.SimpleNamespace(version=types.SimpleNamespace(hip=None)))
    with pytest.raises(RuntimeError, match='configure'):
        unified.infer({'kind': 'backing-vocals', 'source_audio': source}, output)
    monkeypatch.setenv('MTA_AI_VOCAL_MODEL', 'mel_band_roformer_karaoke_gabox_v2.ckpt')
    with pytest.raises(RuntimeError, match='no audio'):
        unified.infer({'kind': 'backing-vocals', 'source_audio': source}, output)
    Separator.outputs = ['../escape.wav']
    with pytest.raises(RuntimeError, match='Unexpected'):
        unified.infer({'kind': 'backing-vocals', 'source_audio': source}, output)
    (tmp_path/'voice.wav').write_bytes(b'a')
    Separator.outputs = ['voice.wav']
    unified.infer({'kind': 'backing-vocals', 'source_audio': source}, output)
    assert (tmp_path/'voice_0.wav').exists()


def test_unified_cli_main(tmp_path, monkeypatch):
    from app import ai_execution_policy as binding, model_license_policy as rights
    monkeypatch.setenv('MTA_DATA_DIR', str(tmp_path/'data'))
    source, output = _staged(tmp_path)
    request = tmp_path/'request.json'
    plan = {'kind': 'whisper', 'source_audio': source}
    request.write_text(json.dumps(plan))
    monkeypatch.setenv(binding.KEY, binding.admitted_env('whisper', rights.evaluate('whisper', plan))[binding.KEY])
    seen = []
    monkeypatch.setattr(unified, 'infer', lambda plan, out: seen.append((plan, out)))
    monkeypatch.setattr(sys, 'argv', ['worker', '--request', str(request), '--output', str(output)])
    unified.main()
    assert seen == [(plan, output)]


@pytest.mark.parametrize('admission', ['missing', 'wrong-kind'])
def test_unified_cli_requires_original_admission(tmp_path, monkeypatch, admission):
    from app import ai_execution_policy as binding, model_license_policy as rights
    monkeypatch.setenv('MTA_DATA_DIR', str(tmp_path/'data'))
    source, output = _staged(tmp_path)
    request = tmp_path/'request.json'
    request.write_text(json.dumps({'kind': 'whisper', 'source_audio': source}))
    monkeypatch.delenv(binding.KEY, raising=False)
    if admission == 'wrong-kind':
        monkeypatch.setenv(binding.KEY, binding.admitted_env('vocal-harmony', rights.evaluate('vocal-harmony', {}))[binding.KEY])
    seen = []
    monkeypatch.setattr(unified, 'infer', lambda *args: seen.append(args))
    monkeypatch.setattr(sys, 'argv', ['worker', '--request', str(request), '--output', str(output)])
    with pytest.raises(ValueError, match='Original admitted worker'):
        unified.main()
    assert seen == [] and not output.exists()
