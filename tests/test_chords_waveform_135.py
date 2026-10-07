from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_native_bundle_explicitly_includes_madmom_chord_modules():
    spec = (ROOT / "native/mta_audio_editor_native.spec").read_text(encoding="utf-8")
    assert '"madmom_infer.features.chords"' in spec
    assert '"madmom_infer.audio.chroma"' in spec
    assert '"madmom_infer.ml.crf"' in spec


def test_chordino_ui_distinguishes_no_model_from_missing_external_engine():
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    assert "runtime Chordino non disponibile" in js
    assert "host Vamp presente · plugin Chordino non rilevato" in js
    assert "nessun modello AI richiesto" in js


def test_waveform_preview_uses_persisted_peaks_without_fetching_audio():
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    start = js.index("async function drawWave(t){")
    end = js.index("\nfunction ", start + 10)
    draw = js[start:end]
    assert "waveform_peaks" in draw
    assert "fetch(" not in draw
    assert "decodeAudioData" not in draw
    assert "columns=Math.max(1,Math.ceil(tw))" in draw
    assert "interpolate between cached peaks" in draw
    assert "sourceStart/durationMs*peaks.length" in draw


def test_madmom_availability_checks_real_lazy_modules():
    src = (ROOT / "app/ai_models.py").read_text(encoding="utf-8")
    assert 'find_spec("madmom_infer.features.chords")' in src
    assert 'find_spec("madmom_infer.audio.chroma")' in src
