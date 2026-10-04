import shutil
import subprocess
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

WRITE = {"X-MTA-Request": "1"}


def test_current_project_type_is_reflected_in_import_split_ui():
    root = Path(__file__).resolve().parents[1]
    js = (root / "app/static/app.js").read_text(encoding="utf-8")
    assert "mode==='existing'&&current?.target" in js
    assert "target.value=current.target" in js
    assert "['DAW','MTA8','MTA16'].includes(current.target)" in js


def test_native_demucs_split_uses_upstream_resolver_not_model_server():
    root = Path(__file__).resolve().parents[1]
    plugins = (root / "app/plugins.py").read_text(encoding="utf-8")
    manager = (root / "native/model_manager.py").read_text(encoding="utf-8")
    split_block = plugins[plugins.index("    def split("):]
    assert "ensure_native_model" not in split_block
    assert 'if getattr(sys, "frozen", False):\n            local_repo = ""' in split_block
    assert "--repo" in split_block  # server/standalone custom repo support remains
    assert "def _headers()->dict[str,str]:\n    headers=_headers()" not in manager
    assert "MTA-Audio-Editor-native-model-manager" in manager


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg required")
def test_import_split_reuses_existing_original_even_when_not_on_timeline(tmp_path, monkeypatch):
    import app.main as main
    import app.storage as storage

    monkeypatch.setattr(storage, "ROOT", tmp_path.resolve())
    monkeypatch.setenv("MTA_ALLOW_INSECURE_NO_AUTH", "true")

    source = tmp_path / "song.mp3"
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=0.3",
        "-ar", "44100", "-ac", "2", "-b:a", "192k", str(source),
    ], check=True)

    project = storage.create_project("Reuse me", "DAW")
    existing = storage.originals_dir(project.id) / "song.mp3"
    existing.write_bytes(source.read_bytes())
    assert project.tracks == []

    captured = {}
    def fake_worker(job_id, source_path, keep):
        captured["source"] = Path(source_path)
        captured["keep"] = keep

    class FakeSplitter:
        @classmethod
        def available(cls): return True
        @classmethod
        def status(cls):
            return {
                "available": True,
                "models": ["htdemucs_6s"],
                "recommended_model": "htdemucs_6s",
                "supported_stem_counts": [2, 4, 6],
                "model_profiles": [{"model":"htdemucs_6s","stem_count":6}],
            }

    monkeypatch.setattr(main, "STEM_SPLITTER", FakeSplitter)
    monkeypatch.setattr(main, "_stem_split_worker", fake_worker)
    with main.STEM_JOB_LOCK:
        main.STEM_JOBS.clear()

    client = TestClient(main.app, headers=WRITE)
    with source.open("rb") as fh:
        response = client.post(
            f"/api/stems/jobs?project_id={project.id}&model=htdemucs_6s&keep_original_track=false",
            files={"file": ("song.mp3", fh, "audio/mpeg")},
        )
    assert response.status_code == 200, response.text
    deadline = time.time() + 2
    while "source" not in captured and time.time() < deadline:
        time.sleep(0.01)
    assert captured["source"].resolve() == existing.resolve()
    assert storage.load_project(project.id).tracks == []
    originals = [x for x in storage.project_files(project.id) if x["category"] == "original"]
    assert [x["name"] for x in originals] == ["song.mp3"]
