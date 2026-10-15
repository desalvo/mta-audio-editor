"""Producer and consumer reject cross-platform stem-name aliases."""
import io
import json
import zipfile



import pytest
from fastapi import HTTPException
from app import main
from app.ai_worker_artifacts import package_artifacts
from test_r208_recovered_stem_import import configure, wav


def test_producer_rejects_case_insensitive_aliases(tmp_path):
    payload = wav()
    (tmp_path / 'Vocals.wav').write_bytes(payload)
    (tmp_path / 'vocals.wav').write_bytes(payload)
    (tmp_path / 'output.manifest.json').write_text(json.dumps({'version': 1, 'files': [
        {'name': 'Vocals.wav', 'type': 'audio/wav'},
        {'name': 'vocals.wav', 'type': 'audio/wav'},
    ]}))
    with pytest.raises(ValueError, match='duplicate'):
        package_artifacts(tmp_path)


def test_consumer_rejects_case_insensitive_aliases_without_mutation(monkeypatch):
    payload = wav()
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, 'w') as z:
        z.writestr('Vocals.wav', payload)
        z.writestr('vocals.wav', payload)
        z.writestr('manifest.json', json.dumps({'version': 1, 'files': [
            {'name': 'Vocals.wav', 'type': 'audio/wav'},
            {'name': 'vocals.wav', 'type': 'audio/wav'},
        ]}))
    project = configure(monkeypatch, bio.getvalue())
    starts = []
    monkeypatch.setattr('app.ai_recovered_stem_transaction.begin', lambda *args: starts.append(args))
    with pytest.raises(HTTPException) as exc:
        main.native_ai_workers_import_recovered_stems(None, 'a' * 32, 'p1')
    assert exc.value.status_code == 422
    assert not starts and not project.tracks
