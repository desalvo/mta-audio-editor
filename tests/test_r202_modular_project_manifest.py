import json
import zipfile
from pathlib import Path

from app import storage


def test_project_link_is_small_json_manifest_not_zip(tmp_path, monkeypatch):
    root = tmp_path / "projects"
    monkeypatch.setattr(storage, "ROOT", root)
    root.mkdir(parents=True, exist_ok=True)
    project = storage.create_project("Manifest")
    link = tmp_path / "Manifest.maeproj"
    storage.write_project_link(project.id, link)
    assert link.is_file()
    assert not zipfile.is_zipfile(link)
    payload = json.loads(link.read_text(encoding="utf-8"))
    assert payload["schema"] == storage.PROJECT_LINK_SCHEMA
    assert payload["project_id"] == project.id
    assert storage.read_project_link(link).id == project.id


def test_legacy_maeproj_zip_is_still_detected_as_portable_archive(tmp_path, monkeypatch):
    root = tmp_path / "projects"
    monkeypatch.setattr(storage, "ROOT", root)
    root.mkdir(parents=True, exist_ok=True)
    project = storage.create_project("Legacy")
    archive = tmp_path / "legacy.maeproj"
    storage.write_project_archive(project.id, archive)
    assert storage.is_portable_project_archive(archive)


def test_native_uses_manifest_for_normal_save_and_maeprojz_for_portable_copy():
    native = Path("native/mta_audio_editor_native.py").read_text(encoding="utf-8")
    assert 'PORTABLE_PROJECT_EXTENSION = ".maeprojz"' in native
    assert "write_project_link(project_id, target)" in native
    assert "MTA Audio Editor Portable Project (*.maeprojz)" in native
    assert "is_portable_project_archive(resolved)" in native
