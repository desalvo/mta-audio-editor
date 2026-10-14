"""Validate the real worker ZIP producer against the recovered-stem importer."""
import hashlib
import json
from pathlib import Path

from app import main
from app.ai_worker_artifacts import package_artifacts
from test_r208_recovered_stem_import import configure, wav


def test_worker_archive_imports_wav_json_and_text_end_to_end(monkeypatch, tmp_path):
    blob = wav()
    components = [('vocals.wav', 'audio/wav', blob),
                  ('notes.json', 'application/json', b'{"engine":"demucs"}'),
                  ('notes.txt', 'text/plain', b'Validated worker output')]
    manifest = {'version': 1, 'files': []}
    for name, media, payload in components:
        (tmp_path / name).write_bytes(payload)
        manifest['files'].append({'name': name, 'type': media, 'sha256': hashlib.sha256(payload).hexdigest()})
    (tmp_path / 'output.manifest.json').write_text(json.dumps(manifest))
    content, media_type = package_artifacts(tmp_path)
    assert media_type == 'application/zip'
    project = configure(monkeypatch, content)
    monkeypatch.setattr(main, '_save_upload', lambda pid, file, rate: ('vocals.wav', tmp_path / 'published.wav', 500))
    monkeypatch.setattr(main, '_register_track_source_in_library', lambda *args: None)
    saves = []
    monkeypatch.setattr(main, 'save_project', lambda p: saves.append(p.model_dump()))
    result = main.native_ai_workers_import_recovered_stems(None, 'a'*32, 'p1')
    assert result['count'] == 1
    assert len(project.tracks) == 1
    assert len(saves) == 1
    assert project.recovered_ai_imports == ['stems:demucs:' + 'a'*32]
