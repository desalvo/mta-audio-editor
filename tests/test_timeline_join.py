"""Joining preserves the audible timeline, source backups and track processing."""
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from app import storage, timeline_media as timeline
from app.audio_engine import render_track
from app.models import Clip
from test_timeline_cross_track import project as project  # noqa: F401


def setup_pair(project, discontinuous=False):
    track = project.tracks[0]
    track.clips = [Clip(id='left', source_start_ms=100, source_end_ms=350, timeline_start_ms=400),
                   Clip(id='right', source_start_ms=600 if discontinuous else 350,
                        source_end_ms=850 if discontinuous else 600, timeline_start_ms=650),
                   Clip(id='later', source_start_ms=900, source_end_ms=1000, timeline_start_ms=1200)]
    track.delay_ms = 37
    track.volume_db = -6
    track.pan = .25
    storage.save_project(project)
    return track


def request(track):
    return timeline.TimelineJoinRequest(track_id=track.id, parts=[
        timeline.TimelinePart(track_id=track.id, clip_id=c.id, filename=track.filename,
                             source_start_ms=c.source_start_ms, source_end_ms=c.source_end_ms,
                             expected_start_ms=c.timeline_start_ms + track.delay_ms)
        for c in track.clips[:2]])


def test_contiguous_source_join_is_metadata_only_and_persists(project):
    track = setup_pair(project)
    original = storage.audio_path(project.id, track.filename).read_bytes()
    result = timeline.join(project, request(track))
    saved = storage.load_project(project.id).tracks[0]
    assert saved.filename == 'one.wav'
    assert storage.audio_path(project.id, saved.filename).read_bytes() == original
    assert [(c.timeline_start_ms, c.source_start_ms, c.source_end_ms) for c in saved.clips] == [(400, 100, 600), (1200, 900, 1000)]
    assert result['clip_ids'] == [saved.clips[0].id]
    assert (saved.delay_ms, saved.volume_db, saved.pan) == (37, -6, .25)


def test_discontinuous_stereo_join_preserves_real_audio_and_later_clip(project, tmp_path):
    track = setup_pair(project, discontinuous=True)
    samples = np.arange(48000) / 48000
    stereo = np.column_stack((.3 * np.sin(2 * np.pi * 400 * samples), .2 * np.cos(2 * np.pi * 700 * samples)))
    sf.write(storage.audio_path(project.id, track.filename), stereo, 48000, subtype='FLOAT')
    track.channels = 2
    storage.save_project(project)
    original = storage.audio_path(project.id, track.filename).read_bytes()
    render_track(track, storage.audio_path(project.id, track.filename), tmp_path / 'before.wav', sample_rate=48000)
    timeline.join(project, request(track))
    saved = storage.load_project(project.id)
    merged = saved.tracks[0]
    assert merged.filename != 'one.wav' and len(merged.clips) == 2
    assert [(c.timeline_start_ms, c.duration_ms) for c in merged.clips] == [(400, 500), (1200, 100)]
    assert (merged.delay_ms, merged.volume_db, merged.pan, merged.channels) == (37, -6, .25, 2)
    assert {asset.filename for asset in saved.clip_library} >= {'one.wav', merged.filename}
    assert storage.audio_path(project.id, 'one.wav').read_bytes() == original
    render_track(merged, storage.audio_path(project.id, merged.filename), tmp_path / 'after.wav', sample_rate=48000)
    before, sr = sf.read(tmp_path / 'before.wav', always_2d=True)
    after, after_sr = sf.read(tmp_path / 'after.wav', always_2d=True)
    assert sr == after_sr == 48000
    np.testing.assert_allclose(after, before, atol=1e-7, rtol=0)
    archive = storage.write_project_archive(project.id, tmp_path / 'joined.maeproj')
    reopened = storage.import_project_archive(archive, None)
    storage.validate_project_files(reopened)
    assert reopened.tracks[0].clips[0].duration_ms == 500
    assert storage.audio_path(reopened.id, 'one.wav').is_file()


@pytest.mark.parametrize('bad', ['gap', 'overlap', 'duplicate', 'source-changed', 'time-changed', 'other-track', 'foreign-file'])
def test_invalid_or_stale_join_has_no_persisted_changes(project, bad):
    track = setup_pair(project)
    req = request(track)
    if bad == 'gap':
        track.clips[1].timeline_start_ms += 1
        req.parts[1].expected_start_ms += 1
        storage.save_project(project)
    elif bad == 'overlap':
        track.clips[1].timeline_start_ms -= 1
        req.parts[1].expected_start_ms -= 1
        storage.save_project(project)
    elif bad == 'duplicate':
        req.parts[1] = req.parts[0].model_copy()
    elif bad == 'source-changed':
        req.parts[0].source_end_ms -= 1
    elif bad == 'time-changed':
        req.parts[0].expected_start_ms += 1
    elif bad == 'other-track':
        req.parts[0].track_id = 'b'
    elif bad == 'foreign-file':
        req.parts[0].filename = 'two.wav'
    before = storage.load_project(project.id).model_dump()
    files = set((storage.pdir(project.id) / 'audio').iterdir())
    with pytest.raises(ValueError):
        timeline.join(project, req)
    assert storage.load_project(project.id).model_dump() == before
    assert set((storage.pdir(project.id) / 'audio').iterdir()) == files


def test_join_decode_failure_removes_new_owned_file_only(project, monkeypatch):
    track = setup_pair(project, discontinuous=True)
    before = storage.load_project(project.id).model_dump()
    files = set((storage.pdir(project.id) / 'audio').iterdir())

    def fail(*args):
        raise ValueError('decode failure')

    monkeypatch.setattr(timeline, '_decode_span', fail)
    with pytest.raises(ValueError, match='decode failure'):
        timeline.join(project, request(track))
    assert storage.load_project(project.id).model_dump() == before
    assert set((storage.pdir(project.id) / 'audio').iterdir()) == files


def test_join_capacity_failure_precedes_new_files(project):
    track = setup_pair(project, discontinuous=True)
    files = set((storage.pdir(project.id) / 'audio').iterdir())

    def reject(owner, size):
        assert size > 65536
        raise ValueError('quota')

    with pytest.raises(ValueError, match='quota'):
        timeline.join(project, request(track), reject)
    assert set((storage.pdir(project.id) / 'audio').iterdir()) == files


def test_production_split_selection_join_payload_and_history():
    root = Path(__file__).resolve().parents[1]
    assert shutil.which('node'), 'Node required for production JavaScript test'
    result = subprocess.run(['node', 'tests/js/timeline_join_split.cjs'], cwd=root, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


def test_join_endpoint_auth_and_persisted_result(project, monkeypatch):
    from app import main
    from fastapi import HTTPException
    from fastapi.testclient import TestClient
    track = setup_pair(project)
    monkeypatch.setenv('MTA_ALLOW_INSECURE_NO_AUTH', 'true')
    client = TestClient(main.app, headers={'X-MTA-Request': '1'})
    response = client.post(f'/api/projects/{project.id}/timeline/join', json=json.loads(request(track).model_dump_json()))
    assert response.status_code == 200, response.text
    assert len(storage.load_project(project.id).tracks[0].clips) == 2

    def denied(*args, **kwargs):
        raise HTTPException(403, 'Forbidden')

    monkeypatch.setattr(main, '_project_for_actor', denied)
    assert client.post(f'/api/projects/{project.id}/timeline/join', json=json.loads(request(track).model_dump_json())).status_code == 403
