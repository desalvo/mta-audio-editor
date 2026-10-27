"""Opt-in native inference routing: fail closed, keep tokens private, validate artifacts."""
import io
import json
import zipfile

import pytest
from app import native_ai_routing as route


def test_independent_native_worker_modes_and_private_tokens(tmp_path,monkeypatch):
    cfg=tmp_path/'config'/'remote.json'
    monkeypatch.setenv('MTA_NATIVE_AI_CONFIG',str(cfg))
    route.configure('whisper','remote','https://mta.example.org','personal-secret')
    assert route.is_remote('whisper')
    assert not route.is_remote('demucs')
    assert 'personal-secret' not in json.dumps(route.public_settings())
    assert cfg.stat().st_mode & 0o777 == 0o600
    route.configure('whisper','remote','https://mta.example.org','')
    assert route.is_remote('whisper')
    route.configure('whisper','local')
    assert not route.is_remote('whisper')


def test_remote_requires_https_and_token(tmp_path,monkeypatch):
    monkeypatch.setenv('MTA_NATIVE_AI_CONFIG',str(tmp_path/'remote.json'))
    with pytest.raises(ValueError): route.configure('whisper','remote','http://mta.example.org','x')
    with pytest.raises(ValueError): route.configure('whisper','remote','https://mta.example.org','')
    with pytest.raises(ValueError): route.configure('whisper','remote','https://mta.example.org','a\nb')


def test_remote_inference_wav_and_json_zip(tmp_path,monkeypatch):
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER', 'true')
    monkeypatch.setenv('MTA_NATIVE_AI_CONFIG',str(tmp_path/'remote.json'))
    route.configure('whisper','remote','https://mta.example.org','secret')
    source=tmp_path/'source.wav';source.write_bytes(b'RIFF' + b'\0'*4+b'WAVE'+b'\0'*12)
    from app import ai_remote_client
    def mock_transport(url,token,kind,wav,options,**kwargs):
        assert token=='secret' and kind=='whisper' and wav.startswith(b'RIFF')
        z=io.BytesIO()
        with zipfile.ZipFile(z,'w') as archive:
            archive.writestr('transcript.json',json.dumps({'lines':[{'time_ms':0,'text':'hello'}]}))
        return z.getvalue(),'application/zip','job-123'
    monkeypatch.setattr(ai_remote_client,'infer_audio',mock_transport)
    result,job_id=route.infer('whisper',source,{'model':'turbo'})
    assert job_id=='job-123' and result['json']['transcript.json']['lines'][0]['text']=='hello'


def test_remote_rejects_unsafe_zip_and_does_not_fallback(tmp_path,monkeypatch):
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER', 'true')
    monkeypatch.setenv('MTA_NATIVE_AI_CONFIG',str(tmp_path/'remote.json'))
    route.configure('demucs','remote','https://mta.example.org','secret')
    source=tmp_path/'source.wav';source.write_bytes(b'RIFF'+b'\0'*4+b'WAVE')
    from app import ai_remote_client
    archive=io.BytesIO()
    with zipfile.ZipFile(archive,'w') as z:z.writestr('../escape.wav',b'RIFFaaaaWAVE')
    monkeypatch.setattr(ai_remote_client,'infer_audio',lambda *a,**kw:(archive.getvalue(),'application/zip','job-1'))
    with pytest.raises(ValueError,match='Unsafe'):route.infer('demucs',source)
    monkeypatch.setattr(ai_remote_client,'infer_audio',lambda *a,**kw: (_ for _ in ()).throw(ai_remote_client.RemoteAIError('offline')))
    # Retrying the same input is read-only after a bad result: no second POST.
    monkeypatch.setattr(ai_remote_client,'recover_after_lost_response',lambda *a,**kw: (_ for _ in ()).throw(ai_remote_client.RemoteAIError('recovery-only')))
    with pytest.raises(ai_remote_client.RemoteAIError,match='recovery-only'):route.infer('demucs',source)
    # A genuinely different request may still be submitted.
    with pytest.raises(ai_remote_client.RemoteAIError,match='offline'):route.infer('demucs',source,{'separation':'new'})

@pytest.mark.parametrize('kind', ['whisper','chords-ml','demucs','drumsep','sam-audio','singer-separation','backing-vocals'])
def test_each_remote_kind_never_uses_local_fallback(kind,tmp_path,monkeypatch):
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER', 'true')
    monkeypatch.setenv('MTA_NATIVE_AI_CONFIG',str(tmp_path/'remote.json'))
    from app import ai_remote_client
    route.configure(kind,'remote','https://mta.example.org','private-token')
    source=tmp_path/'audio.wav';source.write_bytes(b'RIFF'+b'\0'*4+b'WAVE')
    monkeypatch.setattr(ai_remote_client,'infer_audio',lambda *a,**kw: (_ for _ in ()).throw(ai_remote_client.RemoteAIError('remote-offline')))
    with pytest.raises(ai_remote_client.RemoteAIError,match='remote-offline'):
        # Use the licensed DSP route for this transport-only drumsep case.
        route.infer(kind,source,{'model':'dsp'} if kind=='drumsep' else None)
