"""Canonical WAV identity must prevent replay across recovery entry points."""
import asyncio
import io
import wave
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from fastapi.responses import Response
from app import main, ai_arranger_runtime, ai_native_remote_journal


def test_discovery_after_pending_and_reverse(tmp_path, monkeypatch):
    monkeypatch.setattr(ai_arranger_runtime, '_ROOT', tmp_path)
    monkeypatch.setattr(main, '_ace_native_only', lambda _: None)
    project = SimpleNamespace(tracks=[], recovered_ai_imports=[])
    monkeypatch.setattr(main, '_project_for_actor', lambda req, pid: project)
    monkeypatch.setattr(ai_native_remote_journal, 'read_owned_pending', lambda rid: {'kind': 'whisper'})
    out = io.BytesIO()
    with wave.open(out, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(44100); w.writeframes(b'\0\0'*128)
    payload = out.getvalue()
    monkeypatch.setattr(main, 'native_ai_workers_pending_artifact', lambda *args: Response(payload, media_type='audio/wav'))
    monkeypatch.setattr(main, 'native_ai_workers_discovered_artifact', lambda *args: Response(payload, media_type='audio/wav'))
    async def publish(pid, request, uploaded, name='', recovery_receipt=None):
        project.tracks.append(SimpleNamespace(name=name))
        project.recovered_ai_imports.append(recovery_receipt)
        return {'ok': True}
    monkeypatch.setattr(main, '_add_track_under_project_lock', publish)
    one, two = 'a'*32, 'b'*32
    asyncio.run(main.native_ai_workers_import_recovered_wav(object(), one, 'p'))
    project.tracks[0].name = 'Renamed'
    with pytest.raises(HTTPException) as err:
        asyncio.run(main.native_ai_workers_import_discovered_wav(object(), 'whisper', one, 'p'))
    assert err.value.status_code == 409
    asyncio.run(main.native_ai_workers_import_discovered_wav(object(), 'whisper', two, 'p'))
    project.tracks[1].name = 'Renamed again'
    with pytest.raises(HTTPException) as err:
        asyncio.run(main.native_ai_workers_import_recovered_wav(object(), two, 'p'))
    assert err.value.status_code == 409
    assert project.recovered_ai_imports == [f'wav:whisper:{one}', f'wav:whisper:{two}']


def test_legacy_pending_receipt_blocks_both_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(ai_arranger_runtime, '_ROOT', tmp_path)
    monkeypatch.setattr(main, '_ace_native_only', lambda _: None)
    rid = 'e'*32
    project = SimpleNamespace(tracks=[], recovered_ai_imports=[f'wav:pending:{rid}'])
    monkeypatch.setattr(main, '_project_for_actor', lambda *args: project)
    monkeypatch.setattr(ai_native_remote_journal, 'read_owned_pending', lambda rid: {'kind': 'whisper'})
    with pytest.raises(HTTPException) as err:
        asyncio.run(main.native_ai_workers_import_recovered_wav(object(), rid, 'p'))
    assert err.value.status_code == 409
    with pytest.raises(HTTPException) as err:
        asyncio.run(main.native_ai_workers_import_discovered_wav(object(), 'whisper', rid, 'p'))
    assert err.value.status_code == 409
