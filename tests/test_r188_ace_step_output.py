import io
import json
import wave
import pytest
from app import ace_step_http_worker as a

def make_audio():
    data=io.BytesIO()
    with wave.open(data, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100); w.writeframes(b"\x00\x00"*200)
    return data.getvalue()

@pytest.mark.parametrize('returned', [b"<html>oops</html>", b"RIFF", b"", make_audio()[:-10]])
def test_reject_invalid_worker_audio(tmp_path, monkeypatch, returned):
    (tmp_path/'inputs').mkdir()
    (tmp_path/'inputs/master.wav').write_bytes(make_audio())
    req=tmp_path/'request.json'
    req.write_text(json.dumps({'model_id':'ace-step-1.5', 'prompt':'jazz', 'source_audio':[{'filename':'inputs/master.wav'}]}))
    def transport(url, *args, **kwargs):
        if '/release_task' in url: return b'{"data":{"task_id":"t"}}'
        if '/query_result' in url: return b'{"data":[{"task_id":"t","status":1,"result":"[{\\"file\\":\\"/v1/audio?path=out.wav\\"}]"}]}'
        return returned
    # Write status payload as proper JSON without depending on string escaping.
    def endpoint(url, *args, **kwargs):
        if '/query_result' in url:
            return json.dumps({'data':[{'task_id':'t','status':1,'result':[{'file':'/v1/audio?path=out.wav'}]}]}).encode()
        return transport(url, *args, **kwargs)
    monkeypatch.setattr(a, '_request', endpoint)
    with pytest.raises((ValueError, wave.Error, EOFError)):
        a.run(req, tmp_path/'out.wav')
    assert not (tmp_path/'out.wav').exists()

def test_explicit_port_only(monkeypatch):
    monkeypatch.setenv('MTA_ACE_STEP_URL','http://127.0.0.1')
    with pytest.raises(ValueError): a.endpoint_base()
