from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_whisper_turbo_is_default_everywhere():
    ai = (ROOT / "app/ai_models.py").read_text(encoding="utf-8")
    music = (ROOT / "app/music_text.py").read_text(encoding="utf-8")
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    assert 'MTA_LYRICS_WHISPER_MODEL", "turbo"' in ai
    assert music.count('MTA_LYRICS_WHISPER_MODEL", "turbo"') >= 2
    assert "default_model||'turbo'" in js


def test_chord_job_does_not_expose_inline_chords():
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    music = (ROOT / "app/music_text.py").read_text(encoding="utf-8")
    assert 'partial={"kind":"chords","items":[]}' in main
    assert "Multi-stage chord extraction" in music


def test_analysis_dialogs_warn_about_long_processing_time():
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    assert "l’estrazione può richiedere molto tempo" in js
    assert "l’analisi degli accordi può richiedere molto tempo" in js
    assert "Nota sui tempi di elaborazione" in js


def test_native_hides_open_local_project_action():
    html = (ROOT / "app/templates/index.html").read_text(encoding="utf-8")
    css = (ROOT / "app/static/app.css").read_text(encoding="utf-8")
    assert 'id="openLocalProjectBtn"' in html and 'onclick="openLocalProject()" hidden' in html
    assert '.native-single-user .web-project-action{display:none!important}' in css
