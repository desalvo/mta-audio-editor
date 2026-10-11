import json
import wave
from pathlib import Path
import pytest
from app import ace_step_http_worker as adapter


def test_loopback_only(monkeypatch):
    monkeypatch.setenv('MTA_ACE_STEP_URL', 'http://evil.example:8001')
    with pytest.raises(ValueError):
        adapter.endpoint_base()
    monkeypatch.setenv('MTA_ACE_STEP_URL', 'http://127.0.0.1:8001')
    assert adapter.endpoint_base().endswith('8001')


def test_manifest_is_workspace_local(tmp_path):
    (tmp_path/'inputs').mkdir()
    (tmp_path/'inputs'/'master.wav').write_bytes(b'audio')
    request=tmp_path/'request.json'
    assert adapter._source_path(request, {'source_audio':[{'filename':'inputs/master.wav'}]}).name=='master.wav'
    with pytest.raises(ValueError):
        adapter._source_path(request, {'source_audio':[{'filename':'inputs/../request.json'}]})


def test_mock_ace_step_end_to_end(monkeypatch,tmp_path):
    (tmp_path/'inputs').mkdir()
    import io
    buffer=io.BytesIO()
    with wave.open(buffer,'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(44100);f.writeframes(b'\0\0'*200)
    (tmp_path/'inputs'/'master.wav').write_bytes(buffer.getvalue())
    plan={'model_id':'ace-step-1.5','source_audio':[{'filename':'inputs/master.wav'}], 'prompt':'jazz style', 'strength':80}
    request=tmp_path/'request.json'; request.write_text(json.dumps(plan))
    calls=[]
    def fake_request(url,data=None,content_type=None,**kwargs):
        calls.append((url,data,content_type))
        if url.endswith('/release_task'):
            assert b'name="src_audio"' in data
            assert b'0.199999' in data or b'0.2' in data
            return json.dumps({'data':{'task_id':'mock-1'}}).encode()
        if url.endswith('/query_result'):
            return json.dumps({'data':[{'task_id':'mock-1','status':1,'result':'[{"file":"/v1/audio?path=generated.wav"}]'}]}).encode()
        assert url.endswith('/v1/audio?path=generated.wav')
        return buffer.getvalue()
    monkeypatch.setattr(adapter,'_request',fake_request)
    monkeypatch.setenv('MTA_ACE_STEP_URL','http://127.0.0.1:8001')
    output=tmp_path/'output.wav'
    adapter.run(request,output)
    assert output.read_bytes()==buffer.getvalue()
    assert len(calls)==3
