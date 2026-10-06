from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_lyrics_default_is_whisper_turbo():
    ai = (ROOT / "app/ai_models.py").read_text(encoding="utf-8")
    music = (ROOT / "app/music_text.py").read_text(encoding="utf-8")
    assert 'MTA_LYRICS_WHISPER_MODEL", "turbo"' in ai
    assert 'MTA_LYRICS_WHISPER_MODEL' in music and '"turbo"' in music


def test_meta_panel_is_responsive_and_expandable():
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    css = (ROOT / "app/static/app.css").read_text(encoding="utf-8")
    assert "openExpandedMetaPanel()" in js
    assert "showExpandedMetaTab" in js
    assert ".meta-expanded-modal" in css
    assert "flex-wrap:wrap" in css
    assert "white-space:normal" in css


def test_pdf_preview_uses_the_real_generated_pdf():
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    block = js[js.index("async function previewProjectLyricsPdf"):js.index("async function resetTimedData")]
    assert "/lyrics.pdf.preview" in block
    # r179: native WebViews render the real PDF URL directly; blob object URLs produced blank previews.
    assert "response.blob()" not in block
    assert "/lyrics.pdf.preview" in block
    assert "pdf-preview-frame" in block
    assert "pdf-sheet" not in block


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
    assert "estimate_bpm_and_signature(audio_path(pid, track.filename)" in main
    assert "time_signature" in main
