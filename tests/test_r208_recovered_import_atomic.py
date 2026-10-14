import asyncio
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from fastapi.responses import Response
from app import main, ai_arranger_runtime, ai_native_remote_journal

WAV = b'RIFF' + (36).to_bytes(4, 'little') + b'WAVEfmt ' + b'\x00' * 36


def test_atomic_recovered_import_and_duplicate(tmp_path, monkeypatch):
    monkeypatch.setattr(ai_arranger_runtime, '_ROOT', tmp_path)
    monkeypatch.setattr(main, '_ace_native_only', lambda request: None)
    monkeypatch.setattr(ai_native_remote_journal, 'read_owned_pending', lambda rid: {'kind': 'whisper'})
    project = SimpleNamespace(tracks=[], recovered_ai_imports=[])
    monkeypatch.setattr(main, '_project_for_actor', lambda req, pid: project)
    monkeypatch.setattr(main, 'native_ai_workers_pending_artifact', lambda req, rid: Response(WAV, media_type='audio/wav'))
    async def add_track(pid, request, file, name='', **kwargs):
        project.tracks.append(SimpleNamespace(name=name))
        return project
    monkeypatch.setattr(main, '_add_track_under_project_lock', add_track)
    rid='a'*32
    result=asyncio.run(main.native_ai_workers_import_recovered_wav(object(),rid,'project-1'))
    assert len(result.tracks)==1
    with pytest.raises(HTTPException) as caught:
        asyncio.run(main.native_ai_workers_import_recovered_wav(object(),rid,'project-1'))
    assert caught.value.status_code==409
    assert len(result.tracks)==1


@pytest.mark.parametrize('mime,payload,status', [('application/json',b'{}',415),('audio/wav',b'bad',422)])
def test_atomic_recovered_import_rejects_wrong_artifact(tmp_path,monkeypatch,mime,payload,status):
    monkeypatch.setattr(ai_arranger_runtime,'_ROOT',tmp_path)
    monkeypatch.setattr(main,'_ace_native_only',lambda request:None)
    monkeypatch.setattr(main,'_project_for_actor',lambda request,pid:SimpleNamespace(tracks=[], recovered_ai_imports=[]))
    monkeypatch.setattr(ai_native_remote_journal, 'read_owned_pending', lambda rid: {'kind': 'whisper'})
    monkeypatch.setattr(main,'native_ai_workers_pending_artifact',lambda request,rid:Response(payload,media_type=mime))
    with pytest.raises(HTTPException) as caught:
        asyncio.run(main.native_ai_workers_import_recovered_wav(object(),'b'*32,'project-2'))
    assert caught.value.status_code==status


def test_atomic_recovered_import_invalid_id(tmp_path,monkeypatch):
    monkeypatch.setattr(ai_arranger_runtime,'_ROOT',tmp_path)
    monkeypatch.setattr(main,'_ace_native_only',lambda request:None)
    monkeypatch.setattr(main,'_project_for_actor',lambda request,pid:SimpleNamespace(tracks=[], recovered_ai_imports=[]))
    monkeypatch.setattr(ai_native_remote_journal, 'read_owned_pending', lambda rid: {'kind': 'whisper'})
    with pytest.raises(HTTPException) as caught:
        asyncio.run(main.native_ai_workers_import_recovered_wav(object(),'invalid','project-2'))
    assert caught.value.status_code==400
