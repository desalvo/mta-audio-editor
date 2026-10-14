import pytest
from fastapi import HTTPException
from app import ai_native_remote_journal as journal
from app import native_ai_routing as routing
from app import main
from app import ai_remote_client as client


def setup(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_NATIVE_AI_CONFIG', str(tmp_path / 'settings.json'))
    monkeypatch.setenv('MTA_NATIVE_REMOTE_JOURNAL', str(tmp_path / 'pending'))
    monkeypatch.setattr(main, '_ace_native_only', lambda request: None)
    routing.configure('whisper','remote','https://example.org','secret')
    request_id, _, _ = journal.begin('https://example.org','secret','whisper',b'RIFF____WAVE',{})
    return request_id


@pytest.mark.parametrize('mime,content,suffix', [
    ('application/json',b'{"result":true}','json'),
    ('audio/wav',b'RIFF____WAVE','wav'),
    ('application/zip',b'PK\x03\x04result','zip'),
])
def test_download_read_only_keeps_journal(tmp_path, monkeypatch, mime, content, suffix):
    rid=setup(tmp_path,monkeypatch)
    called=[]
    def recovery(url, token, key, **options):
        called.append((url, token, key, options))
        return content,mime,'worker-1'
    monkeypatch.setattr(client,'recover_after_lost_response', recovery)
    response=main.native_ai_workers_pending_artifact(object(),rid)
    assert response.body==content
    assert response.media_type==mime
    assert response.headers['content-disposition'].endswith('.'+suffix+'"')
    assert response.headers['cache-control']=='no-store'
    assert len(called)==1 and called[0][2]==rid
    assert journal.list_pending()[0]['request_id']==rid


def test_changed_settings_fail_closed(tmp_path,monkeypatch):
    rid=setup(tmp_path,monkeypatch)
    routing.configure('whisper','local')
    with pytest.raises(HTTPException) as exc:
        main.native_ai_workers_pending_artifact(object(),rid)
    assert exc.value.status_code==409
    assert len(journal.list_pending())==1


def test_unowned_request_blocked(tmp_path,monkeypatch):
    setup(tmp_path,monkeypatch)
    with pytest.raises(HTTPException) as exc:
        main.native_ai_workers_pending_artifact(object(),'a'*32)
    assert exc.value.status_code==409


def test_recovery_failure_does_not_discard_journal(tmp_path,monkeypatch):
    rid=setup(tmp_path,monkeypatch)
    def fail(*args,**kwargs):raise client.RemoteAIError('still admitted')
    monkeypatch.setattr(client,'recover_after_lost_response',fail)
    with pytest.raises(HTTPException) as exc:
        main.native_ai_workers_pending_artifact(object(),rid)
    assert exc.value.status_code==502
    assert len(journal.list_pending())==1
