"""Real audio, persisted edits and archive round-trips for cross-track editing."""
import shutil

import numpy as np
import pytest
import soundfile as sf

from app import storage, timeline_media as timeline
from app.audio_engine import project_duration_ms, render_track
from app.models import Clip, ProjectClip, Track


@pytest.fixture
def project(tmp_path, monkeypatch):
    if not shutil.which('ffmpeg'):
        pytest.skip('FFmpeg required')
    monkeypatch.setattr(storage, 'ROOT', tmp_path / 'projects')
    p = storage.create_project('Timeline', target='DAW', sample_rate=48000)
    for name, value in [('one.wav', .125), ('two.wav', .5)]:
        sf.write(storage.audio_path(p.id, name), np.full((48000, 1), value, dtype='float32'), 48000, subtype='FLOAT')
    p.tracks = [Track(id='a', name='A', filename='one.wav', channels=1, sample_rate=48000,
        duration_ms=1000, clips_initialized=True, clips=[Clip(id='a1', source_start_ms=100, source_end_ms=600, timeline_start_ms=0)]),
        Track(id='b', name='B', filename='two.wav', channels=1, sample_rate=48000, delay_ms=100,
        duration_ms=1000, clips_initialized=True, clips=[Clip(id='b1', source_start_ms=0, source_end_ms=400, timeline_start_ms=100)])]
    p.clip_library = [ProjectClip(id='one', name='One', filename='one.wav', duration_ms=1000, channels=1),
                      ProjectClip(id='two', name='Two', filename='two.wav', duration_ms=1000, channels=1)]
    storage.save_project(p)
    return p


def request(p, action='copy', start=800):
    return timeline.TimelineTransferRequest(destination_track_id='b', start_ms=start, action=action,
        parts=[timeline.TimelinePart(track_id='a', clip_id='a1', filename='one.wav', source_start_ms=100, source_end_ms=600)])


def test_cross_source_copy_retains_audio_and_timeline_after_reload(project, tmp_path):
    before = storage.audio_path(project.id, 'two.wav').read_bytes()
    result = timeline.transfer(project, request(project))
    saved = storage.load_project(project.id)
    assert len(saved.tracks[0].clips) == 1
    dest = saved.tracks[1]
    assert dest.filename != 'two.wav'
    assert [(c.timeline_start_ms, c.duration_ms) for c in dest.clips] == [(100, 400), (700, 500)]
    assert storage.audio_path(project.id, 'two.wav').read_bytes() == before
    assert {x.filename for x in saved.clip_library} >= {'one.wav', 'two.wav', dest.filename}
    output = tmp_path / 'render.wav'
    render_track(dest, storage.audio_path(saved.id, dest.filename), output, sample_rate=48000)
    samples, rate = sf.read(output, always_2d=True)
    assert rate == 48000
    assert abs(float(samples[12000:24000].mean()) - .5) < .002
    assert abs(float(samples[40800:57600].mean()) - .125) < .002
    assert project_duration_ms(saved) == 1300
    assert result['clip_ids'][0] == dest.clips[-1].id
    # Same render path serves previews, the native fallback and all exports.


def test_move_is_atomic_and_keeps_source_for_undo(project):
    result = timeline.transfer(project, request(project, 'move'))
    saved = storage.load_project(project.id)
    assert saved.tracks[0].clips == [] and saved.tracks[0].clips_initialized
    assert set(result['changed_track_ids']) == {'a', 'b'}
    assert storage.audio_path(saved.id, 'one.wav').exists()
    assert any(x.filename == 'one.wav' for x in saved.clip_library)


def test_overlap_and_stale_moves_leave_project_unchanged(project):
    before = storage.load_project(project.id).model_dump()
    with pytest.raises(ValueError, match='sovrapporsi'):
        timeline.transfer(project, request(project, 'move', 300))
    assert storage.load_project(project.id).model_dump() == before
    bad = request(project, 'move');bad.parts[0].source_end_ms = 601
    with pytest.raises(ValueError, match='cambiato'):
        timeline.transfer(project, bad)
    assert storage.load_project(project.id).model_dump() == before


def test_failed_decode_removes_owned_files_only(project, monkeypatch):
    before = storage.load_project(project.id).model_dump()
    names = set(storage.pdir(project.id).joinpath('audio').iterdir())
    def fail(*args):
        raise RuntimeError('decode failed')
    monkeypatch.setattr(timeline, '_decode_span', fail)
    with pytest.raises(RuntimeError, match='decode failed'):
        timeline.transfer(project, request(project, 'move'))
    assert set(storage.pdir(project.id).joinpath('audio').iterdir()) == names
    assert storage.load_project(project.id).model_dump() == before


def test_empty_track_is_silent_and_accepts_project_audio(project):
    out = timeline.empty_track(project, timeline.EmptyTrackRequest(name='Empty', after_track_id='a'))
    saved = storage.load_project(project.id)
    empty = saved.tracks[1]
    assert empty.id == out['track_id'] and empty.clips == [] and empty.clips_initialized
    assert empty.duration_ms == 0
    assert project_duration_ms(saved) == 600
    req = timeline.TimelineTransferRequest(destination_track_id=empty.id, start_ms=1000,
        parts=[timeline.TimelinePart(filename='one.wav', source_start_ms=0, source_end_ms=1000)])
    timeline.transfer(saved, req)
    new = storage.load_project(project.id).tracks[1]
    assert len(new.clips) == 1 and new.clips[0].timeline_start_ms == 1000
    assert project_duration_ms(storage.load_project(project.id)) == 2000


def test_same_source_moves_do_not_reencode(project):
    project.tracks[1].filename = 'one.wav'
    storage.save_project(project)
    timeline.transfer(project, request(project, 'move'))
    saved = storage.load_project(project.id)
    assert saved.tracks[1].filename == 'one.wav'
    assert len(saved.tracks[1].clips) == 2


def test_source_not_owned_and_past_end_are_rejected(project):
    req = request(project);req.parts[0].filename = 'foreign.wav'
    with pytest.raises(ValueError, match='appartiene'):
        timeline.transfer(project, req)
    req = request(project);req.parts[0].source_end_ms = 2000
    before = storage.load_project(project.id).model_dump()
    with pytest.raises(ValueError, match='fine della sorgente'):
        timeline.transfer(project, req)
    assert storage.load_project(project.id).model_dump() == before


def test_empty_midi_track_respects_project_kind(project):
    with pytest.raises(ValueError, match='does not allow'):
        timeline.empty_track(project, timeline.EmptyTrackRequest(kind='midi'))
    project.target = 'DAW_MIDI'
    result = timeline.empty_track(project, timeline.EmptyTrackRequest(kind='midi'))
    assert storage.load_project(project.id).tracks[-1].kind == 'midi'
    assert result['track_id']


def test_archive_reopen_and_export_include_transferred_audio(project, tmp_path):
    from app.audio_engine import render_track_export
    timeline.transfer(project, request(project, 'move'))
    archive = storage.write_project_archive(project.id, tmp_path / 'timeline.maeproj')
    restored = storage.import_project_archive(archive, None)
    storage.validate_project_files(restored)
    track = restored.tracks[1]
    export = render_track_export(track, storage.audio_path(restored.id, track.filename),
        tmp_path / 'export.wav', sample_rate=48000, wav_bit_depth=24, project=restored)
    audio, rate = sf.read(export, always_2d=True)
    assert rate == 48000 and len(audio) == 62400
    assert abs(float(audio[12000:24000].mean()) - .5 / np.sqrt(2)) < .002
    assert abs(float(audio[40800:57600].mean()) - .125 / np.sqrt(2)) < .002
    assert storage.audio_path(restored.id, 'one.wav').is_file()
    assert storage.audio_path(restored.id, 'two.wav').is_file()


def test_mono_into_stereo_keeps_channel_amplitude(project):
    created = timeline.empty_track(project, timeline.EmptyTrackRequest(name='Stereo'))
    req = request(project);req.destination_track_id = created['track_id'];req.start_ms = 0
    timeline.transfer(storage.load_project(project.id), req)
    dest = storage.load_project(project.id).tracks[-1]
    audio, rate = sf.read(storage.audio_path(project.id, dest.filename), always_2d=True)
    assert audio.shape == (24000, 2) and rate == 48000
    np.testing.assert_array_equal(audio, np.full((24000, 2), .125))


def test_packed_ms_boundaries_do_not_drift_at_44100(project):
    project.sample_rate = 44100
    dest = project.tracks[1]
    dest.clips = [Clip(id=f'old{i}', source_start_ms=i, source_end_ms=i + 1, timeline_start_ms=i) for i in range(25)]
    storage.save_project(project)
    req = timeline.TimelineTransferRequest(destination_track_id='b', start_ms=200,
        parts=[timeline.TimelinePart(filename='one.wav', source_start_ms=0, source_end_ms=1, offset_ms=i) for i in range(25)])
    timeline.transfer(project, req)
    saved = storage.load_project(project.id).tracks[1]
    assert len(saved.clips) == 50
    assert all(c.duration_ms == 1 for c in saved.clips)
    assert saved.duration_ms == 50
    assert sf.info(storage.audio_path(project.id, saved.filename)).frames == 2205


def test_stale_position_and_symlink_sources_are_rejected(project, tmp_path):
    req = request(project, 'move');req.parts[0].expected_start_ms = 200
    with pytest.raises(ValueError, match='cambiato'):
        timeline.transfer(project, req)
    outside = tmp_path / 'outside.wav'
    sf.write(outside, np.zeros(1000), 48000)
    source = storage.audio_path(project.id, 'one.wav')
    source.unlink();source.symlink_to(outside)
    with pytest.raises(ValueError):
        timeline.transfer(project, request(project))


def test_http_empty_and_transfer_routes_enforce_authorization(project, monkeypatch):
    from fastapi import HTTPException
    from fastapi.testclient import TestClient
    from app import main
    monkeypatch.setenv('MTA_ALLOW_INSECURE_NO_AUTH', 'true')
    client = TestClient(main.app, headers={'X-MTA-Request': '1'})
    response = client.post(f'/api/projects/{project.id}/tracks/empty', json={'name': 'HTTP track', 'after_track_id': 'a'})
    assert response.status_code == 200, response.text
    track_id = response.json()['track_id']
    payload = request(project).model_dump();payload['destination_track_id'] = track_id
    response = client.post(f'/api/projects/{project.id}/timeline/transfer', json=payload)
    assert response.status_code == 200, response.text
    before = storage.load_project(project.id).model_dump()
    def deny(*args):
        raise HTTPException(403, 'No access')
    monkeypatch.setattr(main, '_project_for_actor', deny)
    assert client.post(f'/api/projects/{project.id}/tracks/empty', json={'name': 'Denied'}).status_code == 403
    assert client.post(f'/api/projects/{project.id}/timeline/transfer', json=payload).status_code == 403
    assert storage.load_project(project.id).model_dump() == before
