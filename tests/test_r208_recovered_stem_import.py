import hashlib
import io
import json
import wave
import zipfile
from contextlib import nullcontext

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from app import main
from app.models import Project


def wav():
    out = io.BytesIO()
    with wave.open(out, 'wb') as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(44100)
        f.writeframes(b'\0\0' * 100)
    return out.getvalue()


def archive(mutate=None):
    blob = wav()
    spec = {'name': 'vocals.wav', 'type': 'audio/wav', 'sha256': hashlib.sha256(blob).hexdigest()}
    if mutate:
        mutate(spec)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as z:
        z.writestr('vocals.wav', blob)
        z.writestr('manifest.json', json.dumps({'version': 1, 'files': [spec]}))
    return buffer.getvalue()


def configure(monkeypatch, payload, kind='demucs'):
    project = Project(id='p1', title='Test')
    monkeypatch.setattr(main, '_ace_native_only', lambda r: None)
    monkeypatch.setattr(main, '_project_for_actor', lambda r, pid: project)
    monkeypatch.setattr('app.ai_project_lock.project_publication_lock', lambda pid: nullcontext())
    monkeypatch.setattr('app.ai_recovered_stem_transaction.reconcile', lambda pid: {'recovered': False})
    monkeypatch.setattr('app.ai_recovered_stem_transaction.begin', lambda pid, receipt: None)
    monkeypatch.setattr('app.ai_native_remote_journal.read_owned_pending', lambda rid: {'kind': kind})
    monkeypatch.setattr(main, 'native_ai_workers_pending_artifact', lambda r, rid: SimpleNamespace(media_type='application/zip', body=payload))
    return project


def test_import_recovered_stems_once(monkeypatch, tmp_path):
    project = configure(monkeypatch, archive())
    saved = []
    monkeypatch.setattr(main, '_save_upload', lambda pid, file, rate: ('vocals.wav', tmp_path / 'vocals.wav', 500))
    monkeypatch.setattr(main, '_register_track_source_in_library', lambda *args: None)
    monkeypatch.setattr(main, 'save_project', lambda p: saved.append(p.model_dump()))
    result = main.native_ai_workers_import_recovered_stems(None, 'a'*32, 'p1')
    assert result['count'] == 1 and result['journal_preserved']
    assert len(project.tracks) == 1 and len(saved) == 1
    with pytest.raises(HTTPException) as exc:
        main.native_ai_workers_import_recovered_stems(None, 'a'*32, 'p1')
    assert exc.value.status_code == 409


def test_bad_manifest_rejected(monkeypatch):
    configure(monkeypatch, archive(lambda x: x.update(sha256='0'*64)))
    with pytest.raises(HTTPException) as exc:
        main.native_ai_workers_import_recovered_stems(None, 'a'*32, 'p1')
    assert exc.value.status_code == 422


def test_wrong_adapter_rejected(monkeypatch):
    configure(monkeypatch, archive(), kind='whisper')
    with pytest.raises(HTTPException) as exc:
        main.native_ai_workers_import_recovered_stems(None, 'a'*32, 'p1')
    assert exc.value.status_code == 415
