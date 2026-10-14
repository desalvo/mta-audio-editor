"""Explicit no-journal server discovery -> verified project publication."""
import asyncio
import io
import wave
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.responses import Response
from app import main, ai_arranger_runtime


def wav_bytes():
    stream = io.BytesIO()
    with wave.open(stream, 'wb') as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(44100)
        writer.writeframes(b'\x00\x00' * 128)
    return stream.getvalue()


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    monkeypatch.setattr(ai_arranger_runtime, '_ROOT', tmp_path)
    monkeypatch.setattr(main, '_ace_native_only', lambda req: None)
    project = SimpleNamespace(tracks=[], recovered_ai_imports=[])
    monkeypatch.setattr(main, '_project_for_actor', lambda req, pid: project)
    async def add(pid, req, file, name='', **kwargs):
        project.tracks.append(SimpleNamespace(name=name))
        if kwargs.get("recovery_receipt"):
            project.recovered_ai_imports.append(kwargs["recovery_receipt"])
        return {'name': name, 'project': pid}
    monkeypatch.setattr(main, '_add_track_under_project_lock', add)
    return project


def execute(key='a'*32, kind='whisper'):
    return asyncio.run(main.native_ai_workers_import_discovered_wav(object(),kind,key,'target-project'))


def test_explicit_import_and_cross_workflow_duplicate_protection(monkeypatch, prepared):
    monkeypatch.setattr(main, 'native_ai_workers_discovered_artifact',
                        lambda req, kind, rid: Response(wav_bytes(), media_type='audio/wav'))
    result = execute()
    assert result == {'name': 'Recovered AI whisper ' + 'a'*32, 'project': 'target-project'}
    with pytest.raises(HTTPException) as exc:
        execute()
    assert exc.value.status_code == 409
    assert len(prepared.tracks) == 1


@pytest.mark.parametrize('mime,data,status', [
    ('application/json', b'{}', 415),
    ('audio/wav', b'RIFFbad!', 422),
    ('audio/wav', b'', 422),
])
def test_reject_invalid_result_without_project_mutation(monkeypatch, prepared, mime, data, status):
    monkeypatch.setattr(main, 'native_ai_workers_discovered_artifact',
                        lambda req, kind, rid: Response(data, media_type=mime))
    with pytest.raises(HTTPException) as exc:
        execute()
    assert exc.value.status_code == status
    assert prepared.tracks == []


def test_remote_ownership_failure_propagates_without_import(monkeypatch, prepared):
    def no_ownership(*args):
        raise HTTPException(404, 'Unknown request')
    monkeypatch.setattr(main, 'native_ai_workers_discovered_artifact', no_ownership)
    with pytest.raises(HTTPException) as exc:
        execute()
    assert exc.value.status_code == 404 and not prepared.tracks


def test_invalid_kind_and_request_id_never_fetch(monkeypatch, prepared):
    monkeypatch.setattr(main, 'native_ai_workers_discovered_artifact',
                        lambda *args: pytest.fail('Must not fetch'))
    for kind, key, status in [('unknown', 'a'*32, 404), ('whisper', 'invalid', 400)]:
        with pytest.raises(HTTPException) as exc:
            execute(key, kind)
        assert exc.value.status_code == status


def test_ui_has_explicit_project_confirmation_and_no_auto_import():
    from pathlib import Path
    js = (Path(__file__).resolve().parents[1] / 'app/static/app.js').read_text()
    block = js[js.index('async function importNativeDiscoveredWav('):js.index('async function testAiArrangerWorker(){')]
    assert 'confirm(' in block
    assert 'current?.id' in block
    assert "method:'POST'" in block
    assert 'nativePendingImportsInFlight' in block


def test_two_worker_kinds_with_same_remote_id_are_independent(monkeypatch, prepared):
    monkeypatch.setattr(main, 'native_ai_workers_discovered_artifact',
                        lambda req, kind, rid: Response(wav_bytes(), media_type='audio/wav'))
    first = execute(kind='whisper')
    second = execute(kind='demucs')
    assert first['name'] != second['name']
    assert len(prepared.tracks) == 2
    with pytest.raises(HTTPException) as exc:
        execute(kind='demucs')
    assert exc.value.status_code == 409


def test_renaming_track_does_not_allow_duplicate_import(monkeypatch, prepared):
    monkeypatch.setattr(main, 'native_ai_workers_discovered_artifact',
                        lambda req, kind, rid: Response(wav_bytes(), media_type='audio/wav'))
    execute()
    prepared.tracks[0].name = 'Renamed by operator'
    with pytest.raises(HTTPException) as exc:
        execute()
    assert exc.value.status_code == 409
    assert len(prepared.tracks) == 1
    assert prepared.recovered_ai_imports == ['wav:whisper:' + 'a'*32]
