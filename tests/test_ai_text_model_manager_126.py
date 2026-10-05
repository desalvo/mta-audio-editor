from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_text_model_catalog_defaults_and_storage(monkeypatch, tmp_path):
    monkeypatch.setenv("MTA_DATA_DIR", str(tmp_path))
    from app.ai_models import ai_catalog
    catalog = ai_catalog(native=False)
    assert catalog["storage"] == "server"
    assert catalog["lyrics"]["default_model"] == "large-v3"
    assert any(item["id"] == "large-v3" for item in catalog["lyrics"]["models"])
    assert catalog["chords"]["default_engine"] == "madmom-deep-chroma"
    assert any(item["id"] == "madmom-deep-chroma" for item in catalog["chords"]["engines"])


def test_project_persists_text_analysis_provenance():
    from app.models import Project
    p = Project(id="p", title="Song")
    p.lyrics_engine = "OpenAI Whisper"
    p.lyrics_model = "large-v3"
    p.chords_engine = "madmom-cnn-crf"
    p.chords_model = "madmom-cnn-crf"
    copy = Project.model_validate(p.model_dump())
    assert copy.lyrics_model == "large-v3"
    assert copy.chords_engine == "madmom-cnn-crf"


def test_web_ui_discloses_chord_engine_and_model_selection():
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    assert "Motore che verrà usato" in js
    assert "stemLyricsModel" in js
    assert "stemChordsEngine" in js
    assert "lyrics_model=${encodeURIComponent(lyricsModel)}" in js
    assert "chords_engine=${encodeURIComponent(chordsEngine)}" in js
    assert "Manage Lyrics / Chords models" in js


def test_chord_runtime_is_packaged_for_server_and_native():
    req = (ROOT / "requirements-chords.txt").read_text(encoding="utf-8")
    assert "madmom-infer @ https://github.com/openmirlab/madmom-infer/archive/" in req
    assert "bffead9be61857fd44b2e0d3a2510d9d94c8f2d2" in req
    docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    spec = (ROOT / "native/mta_audio_editor_native.spec").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/ci-cd.yml").read_text(encoding="utf-8")
    assert "requirements-chords.txt" in docker
    assert "madmom_infer" in spec
    assert "pip install -r requirements-chords.txt" in workflow
