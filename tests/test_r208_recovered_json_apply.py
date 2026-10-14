import io
import json
import zipfile
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from app import main
from app.models import Project


def _project():
    return Project(id='p1', title='Test')


@pytest.mark.parametrize('kind,filename,field,value', [
    ('whisper', 'transcript.json', 'lines', {'time_ms': 1000, 'text': 'hello'}),
    ('chords-ml', 'chords.json', 'chords', {'time_ms': 1000, 'chord': 'C'}),
])
def test_recovered_json_saved_once(kind, filename, field, value, tmp_path, monkeypatch):
    from contextlib import nullcontext
    project = _project()
    request_id = 'a' * 32
    doc = json.dumps({field: [value]}).encode()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as z:
        z.writestr(filename, doc)
    monkeypatch.setattr(main, '_ace_native_only', lambda request: None)
    monkeypatch.setattr(main, '_project_for_actor', lambda request, pid: project)
    monkeypatch.setattr(main, 'save_project', lambda updated: None)
    monkeypatch.setattr('app.ai_project_lock.project_publication_lock', lambda pid: nullcontext())
    monkeypatch.setattr('app.ai_native_remote_journal.read_owned_pending', lambda rid: {'kind': kind})
    monkeypatch.setattr(main, 'native_ai_workers_pending_artifact', lambda request, rid: SimpleNamespace(media_type='application/zip', body=buffer.getvalue()))
    result = main.native_ai_workers_import_recovered_json(None, request_id, 'p1')
    assert result['count'] == 1
    assert f'{kind}:{request_id}' in project.recovered_ai_imports
    with pytest.raises(HTTPException) as exc:
        main.native_ai_workers_import_recovered_json(None, request_id, 'p1')
    assert exc.value.status_code == 409


def test_recovered_json_rejects_unsupported_kind(monkeypatch):
    monkeypatch.setattr(main, '_ace_native_only', lambda request: None)
    monkeypatch.setattr(main, '_project_for_actor', lambda request, pid: _project())
    monkeypatch.setattr('app.ai_native_remote_journal.read_owned_pending', lambda rid: {'kind': 'demucs'})
    with pytest.raises(HTTPException) as exc:
        main.native_ai_workers_import_recovered_json(None, 'b'*32, 'p1')
    assert exc.value.status_code == 415

@pytest.mark.parametrize('members', [
    [('transcript.json', b'{}'), ('transcript.json', b'{}')],
    [('transcript.json', b'{}'), ('../other.json', b'{}')],
    [('transcript.json', b'{}'), ('unlisted.txt', b'{}')],
    [('transcript.json', b'{}'), ('nested/../manifest.json', b'{}')],
])
def test_recovered_json_fails_closed_on_unsafe_archive(monkeypatch, members):
    from contextlib import nullcontext
    project = _project()
    data = io.BytesIO()
    with zipfile.ZipFile(data, 'w') as archive:
        for name, content in members:
            archive.writestr(name, content)
    monkeypatch.setattr(main, '_ace_native_only', lambda request: None)
    monkeypatch.setattr(main, '_project_for_actor', lambda request, pid: project)
    monkeypatch.setattr('app.ai_project_lock.project_publication_lock', lambda pid: nullcontext())
    monkeypatch.setattr('app.ai_native_remote_journal.read_owned_pending', lambda rid: {'kind': 'whisper'})
    monkeypatch.setattr(main, 'native_ai_workers_pending_artifact', lambda request, rid: SimpleNamespace(media_type='application/zip', body=data.getvalue()))
    with pytest.raises(HTTPException) as error:
        main.native_ai_workers_import_recovered_json(None, 'a' * 32, 'p1')
    assert error.value.status_code == 422
    assert project.lyrics == []
    assert project.recovered_ai_imports == []


def test_recovered_json_rejects_zip_symlink(monkeypatch):
    from contextlib import nullcontext
    project = _project()
    data = io.BytesIO()
    with zipfile.ZipFile(data, 'w') as archive:
        entry = zipfile.ZipInfo('transcript.json')
        entry.create_system = 3
        entry.external_attr = 0o120777 << 16
        archive.writestr(entry, b'{"lines": [{"time_ms": 1000, "text": "hello"}]}')
    monkeypatch.setattr(main, '_ace_native_only', lambda request: None)
    monkeypatch.setattr(main, '_project_for_actor', lambda request, pid: project)
    monkeypatch.setattr('app.ai_project_lock.project_publication_lock', lambda pid: nullcontext())
    monkeypatch.setattr('app.ai_native_remote_journal.read_owned_pending', lambda rid: {'kind': 'whisper'})
    monkeypatch.setattr(main, 'native_ai_workers_pending_artifact', lambda request, rid: SimpleNamespace(media_type='application/zip', body=data.getvalue()))
    with pytest.raises(HTTPException) as error:
        main.native_ai_workers_import_recovered_json(None, 'a' * 32, 'p1')
    assert error.value.status_code == 422
    assert project.recovered_ai_imports == []
