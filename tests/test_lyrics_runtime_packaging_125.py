from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_docker_bundles_lyrics_engine():
    docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "requirements-lyrics.txt" in docker
    assert "pip install --no-cache-dir -r requirements-lyrics.txt" in docker
    assert "import fastapi, uvicorn, numpy, whisper" in docker


def test_native_ci_installs_lyrics_engine():
    workflow = (ROOT / ".github/workflows/ci-cd.yml").read_text(encoding="utf-8")
    assert workflow.count("pip install -r requirements-lyrics.txt") >= 2
    assert "pip-audit -r requirements-lyrics.txt --strict" in workflow


def test_pyinstaller_collects_whisper():
    spec = (ROOT / "native/mta_audio_editor_native.spec").read_text(encoding="utf-8")
    assert '"whisper"' in spec


def test_ui_explains_first_model_download():
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    assert "download modello al primo uso" in js
