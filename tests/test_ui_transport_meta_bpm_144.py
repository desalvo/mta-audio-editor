from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_lyrics_default_is_whisper_base():
    ai = (ROOT / "app/ai_models.py").read_text(encoding="utf-8")
    music = (ROOT / "app/music_text.py").read_text(encoding="utf-8")
    assert 'MTA_LYRICS_WHISPER_MODEL", "base"' in ai
    assert 'MTA_LYRICS_WHISPER_MODEL' in music and '"base"' in music


def test_meta_panel_is_responsive_and_expandable():
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    css = (ROOT / "app/static/app.css").read_text(encoding="utf-8")
    assert "openExpandedMetaPanel()" in js
    assert "showExpandedMetaTab" in js
    assert ".meta-expanded-modal" in css
    assert "flex-wrap:wrap" in css
    assert "white-space:normal" in css


def test_pdf_preview_uses_webview_safe_html_sheet():
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    assert "pdf-sheet" in js
    assert "pdf-preview-frame" not in js[js.index("function previewProjectLyricsPdf"):js.index("async function resetTimedData")]


def test_fast_playback_and_spacebar_regressions():
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    assert "canDirectPlayTrack" in js
    assert "/audio/${encodeURIComponent(track.filename)}" in js
    assert "e.key==='Spacebar'" in js
    assert "playbackBuffering)stopPlayback()" in js
    assert "renderedMasterRefreshQueued" in js


def test_track_context_can_recalculate_bpm():
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    main = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert "Ricalcola BPM da questa traccia" in js
    assert "recalculateBpmFromTrack" in js
    assert '@app.post("/api/projects/{pid}/tracks/{track_id}/estimate-bpm")' in main
    assert "estimate_bpm(audio_path(pid, track.filename))" in main
