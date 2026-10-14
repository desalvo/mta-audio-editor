"""Pending WAL import cannot be replayed after a user renames the new track."""
import asyncio
import io
import wave
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from fastapi.responses import Response
from app import main, ai_arranger_runtime, ai_native_remote_journal


def test_pending_wav_receipt_survives_rename(tmp_path, monkeypatch):
    monkeypatch.setattr(ai_arranger_runtime, '_ROOT', tmp_path)
    monkeypatch.setattr(main, '_ace_native_only', lambda request: None)
    project = SimpleNamespace(tracks=[], recovered_ai_imports=[])
    monkeypatch.setattr(main, '_project_for_actor', lambda req, pid: project)
    out = io.BytesIO()
    with wave.open(out, 'wb') as writer:
        writer.setnchannels(1); writer.setsampwidth(2); writer.setframerate(44100)
        writer.writeframes(b'\0\0'*128)
    monkeypatch.setattr(main, 'native_ai_workers_pending_artifact',
                        lambda req, rid: Response(out.getvalue(), media_type='audio/wav'))
    async def publish(pid, request, uploaded, name='', recovery_receipt=None):
        project.tracks.append(SimpleNamespace(name=name))
        project.recovered_ai_imports.append(recovery_receipt)
        return {'ok': True}
    monkeypatch.setattr(main, '_add_track_under_project_lock', publish)
    monkeypatch.setattr(ai_native_remote_journal, 'read_owned_pending', lambda rid: {'kind': 'whisper'})
    rid = 'c'*32
    assert asyncio.run(main.native_ai_workers_import_recovered_wav(object(), rid, 'project'))['ok']
    project.tracks[0].name = 'Renamed'
    with pytest.raises(HTTPException) as ex:
        asyncio.run(main.native_ai_workers_import_recovered_wav(object(), rid, 'project'))
    assert ex.value.status_code == 409
    assert project.recovered_ai_imports == ['wav:whisper:'+rid]
