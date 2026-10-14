"""Recovered WAV imports must retain collision-resistant request identities."""
from pathlib import Path


def test_recovered_track_uses_complete_request_identifier():
    root = Path(__file__).resolve().parents[1]
    source = (root / 'app/main.py').read_text()
    start = source.index("@app.post('/api/native/ai-workers/pending/{request_id}/import-wav/{pid}')")
    end = source.index("@app.post('/api/native/ai-workers/pending/{request_id}/import-json/{pid}')", start)
    block = source[start:end]
    assert "track_name = f'Recovered AI {kind} {request_id}'" in block
    assert "track_name = 'Recovered AI ' + request_id[:12]" not in block
    assert 'project_publication_lock(pid)' in block
    assert 'any(track.name == track_name' in block
    assert 'legacy_receipt in' in block


def test_native_selection_matches_complete_identity():
    root = Path(__file__).resolve().parents[1]
    source = (root / 'app/static/app.js').read_text()
    start = source.index('async function importNativePendingAudio(')
    end = source.index('async function importNativePendingJson(', start)
    block = source[start:end]
    assert 'Recovered AI ${id}' in block
    assert 'Recovered AI ${id.slice(0,12)}' not in block


def test_ci_quality_job_has_extended_timeout():
    root = Path(__file__).resolve().parents[1]
    source = (root / '.github/workflows/ci-cd.yml').read_text()
    quality = source.split('  quality:', 1)[1].split('  vst3-sdk-compile:', 1)[0]
    assert 'timeout-minutes: 150' in quality
    assert '--cov-fail-under=70' in quality
