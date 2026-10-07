import wave
from pathlib import Path

import numpy as np

from app import audio_engine
from app.models import Track

ROOT = Path(__file__).resolve().parents[1]


def test_waveform_cache_capacity_supports_signed_minmax_v2():
    values = [-1.0, 1.0] * 4096
    track = Track(id="t", name="T", filename="t.wav", waveform_peaks=values)
    assert len(track.waveform_peaks) == 8192


def test_waveform_peaks_returns_signed_minmax_envelope(tmp_path, monkeypatch):
    source = tmp_path / "source.wav"
    rate = 8000
    samples = np.array([0, 12000, -6000, 3000, -16000, 4000, 0, -2000] * 1000, dtype=np.int16)
    with wave.open(str(source), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(samples.tobytes())

    def fake_run(cmd, *args, **kwargs):
        destination = Path(cmd[-1])
        destination.write_bytes(source.read_bytes())

    monkeypatch.setattr(audio_engine, "_run", fake_run)
    envelope = audio_engine.waveform_peaks(source, points=256)
    assert len(envelope) == 512
    lows = envelope[0::2]
    highs = envelope[1::2]
    assert min(lows) < 0
    assert max(highs) > 0
    assert all(-1.0 <= value <= 1.0 for value in envelope)
    assert all(lo <= hi for lo, hi in zip(lows, highs))


def test_timeline_waveform_renderer_uses_signed_envelope_and_fill():
    js = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
    start = js.index("async function drawWave(t){")
    end = js.index("\nfunction setZoom", start)
    draw = js[start:end]
    assert "signedEnvelope" in draw
    assert "peaks[i*2]" in draw
    assert "peaks[i*2+1]" in draw
    assert "ctx.fill()" in draw
    assert "sourceStart/durationMs*bins" in draw
    assert "columns=Math.max(1,Math.ceil(tw))" in draw


def test_waveform_revision_invalidates_legacy_cache_format():
    src = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert '"waveform_format": "signed-minmax-v2-4096"' in src
