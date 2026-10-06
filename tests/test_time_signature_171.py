from pathlib import Path

from app.models import Project
from app.music_text import build_lyrics_pdf


def test_project_default_time_signature():
    p = Project(id="p", title="Song")
    assert p.time_signature == "4/4"


def test_project_accepts_supported_time_signatures():
    p = Project(id="p", title="Song", time_signature="3/4")
    assert p.time_signature == "3/4"


def test_lyrics_pdf_signature_parameter(tmp_path: Path):
    out = tmp_path / "lyrics.pdf"
    build_lyrics_pdf(out, title="Song", artist="", lyrics=[], chords=[], bpm=120, time_signature="3/4")
    assert out.is_file() and out.stat().st_size > 0


def test_meter_estimator_prefers_default_on_ambiguous_pattern():
    import numpy as np
    from app.audio_engine import _estimate_meter

    onset = np.zeros(800, dtype=float)
    onset[::50] = 1.0
    assert _estimate_meter(onset, 100.0, 50, "4/4") in {"4/4", "2/4"}


def test_project_rejects_unknown_time_signature():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Project(id="p", title="Song", time_signature="11/16")
