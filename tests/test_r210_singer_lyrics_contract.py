"""Regression for independent source lyrics in native/web Vocal Studio."""
from pathlib import Path
import pytest
from pydantic import ValidationError
from app.studio_jobs import StudioRequest


def test_independent_lyrics_kept_by_track_identifier():
    req=StudioRequest(operation='vocal-synthesis',track_ids=['singer-b','singer-a'],end_ms=10000,
        settings={'language':'en','syllables':[]},singer_lyrics={'singer-b':['one','two'],'singer-a':['hey']})
    assert req.singer_lyrics['singer-a']==['hey']
    assert req.model_dump()['singer_lyrics']['singer-b']==['one','two']


def test_lyrics_budget_rejects_too_many_tracks():
    with pytest.raises(ValidationError):
        StudioRequest(operation='vocal-synthesis',track_ids=['s'],end_ms=1000,
                      singer_lyrics={str(i):['la'] for i in range(33)})


def test_ui_and_worker_both_support_per_singer_lyrics():
    script=(Path(__file__).resolve().parents[1]/'app/static/ai_studio.js').read_text()
    assert 'data-singer-lyrics' in script and 'request.singer_lyrics' in script
    backend=(Path(__file__).resolve().parents[1]/'app/studio_jobs.py').read_text()
    assert "source_settings['syllables']=request.singer_lyrics[tid]" in backend
    assert 'set(body.singer_lyrics)!=set(body.track_ids)' in backend
