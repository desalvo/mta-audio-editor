import json
import zipfile
from pathlib import Path

from app import storage
from app.models import Project, Track

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "app/static/app.css").read_text(encoding="utf-8")
JS = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
MAIN = (ROOT / "app/main.py").read_text(encoding="utf-8")
SAMPLE = (ROOT / "app/sample_editor.py").read_text(encoding="utf-8")


def _project(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "ROOT", tmp_path / "projects")
    storage.ROOT.mkdir(parents=True, exist_ok=True)
    project = Project(id="abc123abc123", title="r210")
    project.tracks = [Track(id="track-a", name="A", filename="a.wav", duration_ms=1000)]
    base = storage.pdir(project.id)
    (base / "audio").mkdir(parents=True, exist_ok=True)
    (base / "audio" / "a.wav").write_bytes(b"audio")
    storage.save_project(project)
    return project


def test_session_preview_root_is_outside_project_workspace(tmp_path, monkeypatch):
    project = _project(tmp_path, monkeypatch)
    cache = storage.session_preview_dir(project.id)
    assert storage.pdir(project.id).resolve() not in cache.resolve().parents
    assert cache.name == project.id


def test_open_cleanup_removes_all_legacy_previews(tmp_path, monkeypatch):
    project = _project(tmp_path, monkeypatch)
    base = storage.pdir(project.id)
    legacy = base / ".preview"
    legacy.mkdir()
    (legacy / "track-a-old.wav").write_bytes(b"preview")
    (base / "preview-master.mp3").write_bytes(b"master")
    (base / ".sample-fx-old.mp3").write_bytes(b"fx")
    result = storage.cleanup_project_preview_cache(project.id, keep_per_track=99)
    assert result == {"preview_deleted": 3, "preview_kept": 0}
    assert not legacy.exists()
    assert not (base / "preview-master.mp3").exists()
    assert not list(base.glob(".sample-fx-*"))


def test_portable_export_excludes_legacy_previews(tmp_path, monkeypatch):
    project = _project(tmp_path, monkeypatch)
    base = storage.pdir(project.id)
    (base / ".preview").mkdir()
    (base / ".preview" / "x.wav").write_bytes(b"x")
    (base / "preview-master.mp3").write_bytes(b"x")
    (base / ".sample-fx-x.mp3").write_bytes(b"x")
    archive = tmp_path / "project.maeprojz"
    storage.write_project_archive(project.id, archive)
    with zipfile.ZipFile(archive) as z:
        names = set(z.namelist())
    assert "project/project.json" in names
    assert not any("/.preview/" in name for name in names)
    assert not any(name.endswith("/preview-master.mp3") for name in names)
    assert not any("/.sample-fx-" in name for name in names)


def test_legacy_import_ignores_preview_payloads(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "ROOT", tmp_path / "projects")
    storage.ROOT.mkdir(parents=True, exist_ok=True)
    project = Project(id="abc123abc123", title="legacy")
    project.tracks = [Track(id="track-a", name="A", filename="a.wav", duration_ms=1000)]
    archive = tmp_path / "legacy.maeproj"
    manifest = {"schema": storage.PROJECT_ARCHIVE_SCHEMA, "project_id": project.id, "title": project.title, "owner_user_id": None, "includes_originals": True}
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("archive-manifest.json", json.dumps(manifest))
        z.writestr("project/project.json", project.model_dump_json())
        z.writestr("project/audio/a.wav", b"audio")
        z.writestr("project/.preview/track-a-old.wav", b"preview")
        z.writestr("project/preview-master.mp3", b"preview")
    imported = storage.import_project_archive(archive, None)
    base = storage.pdir(imported.id)
    assert (base / "audio" / "a.wav").exists()
    assert not (base / ".preview").exists()
    assert not (base / "preview-master.mp3").exists()


def test_preview_endpoints_and_sample_editor_use_session_cache():
    assert 'cache = session_preview_dir(pid) / "tracks"' in MAIN
    assert 'out = session_preview_dir(pid) / "preview-master.mp3"' in MAIN
    assert 'storage.session_preview_dir(project.id) if preview else storage.pdir(project.id)' in SAMPLE
    assert '@app.delete("/api/projects/{pid}/preview-cache")' in MAIN
    assert '_cleanup_session_previews_on_shutdown' in MAIN
    assert "function releaseProjectPreviewCache(projectId)" in JS
    assert "releaseProjectPreviewCache(closingProjectId);" in JS
    assert "window.addEventListener('pagehide'" in JS


def test_plugin_inspector_is_absolute_overlay_and_grid_has_no_inspector_column():
    assert '/* r210: Plugins/Inspector is a true overlay outside editor grid geometry. */' in CSS
    assert '.inspector{position:absolute!important;top:0;right:0;bottom:0;' in CSS
    assert 'grid-template-columns:var(--track-column-width,225px) 5px minmax(540px,1fr)}' in CSS
    r210 = CSS[CSS.index('/* r210: Plugins/Inspector') :]
    assert 'position:absolute!important' in r210
    assert 'width:min(360px,42vw)' in r210
