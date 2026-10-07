from pathlib import Path

import numpy as np

from app.models import Chord
from app.music_text import _chord_pitch_classes, _chord_templates, _refine_extended_harmony


def test_extended_chord_vocabulary_contains_complex_qualities():
    names = {name for name, _ in _chord_templates()}
    for label in ["C7", "Cmaj7", "Cm7", "Cdim7", "Cm7b5", "Caug", "C9", "Cmaj9", "Cm9", "C7b9", "C7#9"]:
        assert label in names


def test_chord_pitch_classes_understand_extended_qualities():
    assert _chord_pitch_classes("Cm7b5") == {0, 3, 6, 10}
    assert _chord_pitch_classes("Cdim7") == {0, 3, 6, 9}
    assert _chord_pitch_classes("C7b9") == {0, 1, 4, 7, 10}


def test_harmonic_refinement_can_emit_slash_bass(monkeypatch, tmp_path):
    # Stable C-major chroma with E dominating bass => C/E.
    times = [0, 250, 500, 750, 1000]
    chroma = np.zeros((5, 12), dtype=np.float64)
    chroma[:, [0, 4, 7]] = [1.0, 0.88, 0.78]
    bass = np.zeros((5, 12), dtype=np.float64)
    bass[:, 4] = 1.0
    bass[:, 0] = 0.25
    energy = np.ones(5, dtype=np.float64)
    monkeypatch.setattr("app.music_text._harmonic_features", lambda *a, **k: (times, chroma, bass, energy))
    dummy = tmp_path / "dummy.wav"
    dummy.write_bytes(b"stub")
    result = _refine_extended_harmony(dummy, [Chord(time_ms=0, chord="C")])
    assert result
    assert result[0].chord == "C/E"


def test_progressive_pipeline_reports_multiple_harmonic_steps():
    source = Path("app/music_text.py").read_text(encoding="utf-8")
    for token in ["Step 1/5", "Step 2/5", "Analisi basso e inversioni / slash chords", "Step 5/5"]:
        assert token in source


def _write_tone_wav(path: Path, freqs: list[float], seconds: float = 1.5, sr: int = 44100):
    import wave
    t = np.arange(int(seconds * sr), dtype=np.float64) / sr
    audio = np.zeros_like(t)
    for idx, freq in enumerate(freqs):
        audio += np.sin(2 * np.pi * freq * t) * (0.45 / (idx + 1) ** 0.35)
    audio /= max(1.0, float(np.max(np.abs(audio))))
    pcm = (audio * 30000).astype(np.int16)
    with wave.open(str(path), "wb") as h:
        h.setnchannels(1); h.setsampwidth(2); h.setframerate(sr); h.writeframes(pcm.tobytes())


def test_harmonic_features_runs_on_real_pcm(tmp_path):
    from app.music_text import _harmonic_features
    wav = tmp_path / "c-major.wav"
    _write_tone_wav(wav, [65.406, 130.813, 261.626, 329.628, 391.995])
    times, chroma, bass, energy = _harmonic_features(wav, interval_ms=250)
    assert len(times) == len(chroma) == len(bass) == len(energy)
    assert len(times) >= 4
    assert chroma.shape[1] == bass.shape[1] == 12
    assert np.max(energy) > 0
    assert int(np.argmax(np.mean(bass, axis=0))) in {0, 7}


def test_refine_real_pcm_returns_extended_events_and_progress(tmp_path):
    wav = tmp_path / "c7.wav"
    _write_tone_wav(wav, [65.406, 130.813, 261.626, 329.628, 391.995, 466.164], seconds=2.0)
    updates = []
    out = _refine_extended_harmony(
        wav, [Chord(time_ms=0, chord="C")], progress=lambda p, i, m: updates.append((p, m))
    )
    assert out and out[0].chord.startswith("C")
    assert any(p == 52 for p, _ in updates)
    assert any(p == 78 for p, _ in updates)
    assert any(p == 86 for p, _ in updates)


def test_refine_missing_file_preserves_base_and_reports_fallback(tmp_path):
    updates = []
    base = [Chord(time_ms=0, chord="Am")]
    out = _refine_extended_harmony(
        tmp_path / "missing.wav", base, progress=lambda p, i, m: updates.append((p, m))
    )
    assert out == base
    assert updates[-1][0] == 90


def test_refine_honours_cancellation(monkeypatch, tmp_path):
    dummy = tmp_path / "exists.wav"
    dummy.write_bytes(b"stub")
    monkeypatch.setattr(
        "app.music_text._harmonic_features",
        lambda *a, **k: ([0], np.ones((1, 12)), np.ones((1, 12)), np.ones(1)),
    )
    try:
        _refine_extended_harmony(dummy, [Chord(time_ms=0, chord="C")], cancelled=lambda: True)
    except InterruptedError:
        pass
    else:
        raise AssertionError("expected cancellation")
