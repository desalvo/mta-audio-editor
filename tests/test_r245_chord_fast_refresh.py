from pathlib import Path


def test_chord_refresh_does_not_wait_for_native_sync():
    js = (Path(__file__).parents[1] / "app/static/app.js").read_text()
    assert "await enqueueChordsRefresh(" in js
    assert "void syncNativeProjectFile(projectId)" in js
    assert "await syncNativeProjectFile(saved.id);refreshMetaPanels()" not in js


def test_chords_waveform_fast_region():
    from app.audio_engine import refresh_chords_waveform_region
    import wave
    import tempfile
    import numpy as np

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "chords.wav"
        values = np.zeros((44100, 2), dtype=np.int16)
        values[22050:33075] = 12000
        with wave.open(str(path), "wb") as handle:
            handle.setnchannels(2)
            handle.setsampwidth(2)
            handle.setframerate(44100)
            handle.writeframes(values.tobytes())
        old = [0.0] * 8192
        updated = refresh_chords_waveform_region(path, old, 500, 750)
        assert len(updated) == len(old)
        assert updated[2 * 2048 + 1] > 0
        assert updated[2 * 100 + 1] == 0
