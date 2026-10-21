"""Real publication, replay/stale guards, independent MIDI parts and harmony."""
import uuid

from fastapi.testclient import TestClient
import pytest

from app import storage
from app.main import app
from app.models import Chord, MidiNote
from app.music_interchange import MusicResult
from app.music_publication import revision
from app.vocal_harmony import arrange


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'ROOT', tmp_path/'projects')
    storage.ROOT.mkdir()
    monkeypatch.setenv('MTA_ALLOW_INSECURE_NO_AUTH', 'true')
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER', 'true')
    return storage.create_project('Musical interchange', target='DAW_MIDI')


def result(count=16):
    return {'parts': [{'id': f'part-{i}', 'name': 'Instrument', 'program': i,
                       'source_model': 'test-fixture', 'notes': [{'id': f'n{i}', 'pitch': 48+i,
                       'start_ms': 100, 'duration_ms': 400, 'origin': 'predicted'}]} for i in range(count)],
            'offset_ms': 750}


def publish(project, data, key=None, expected=None):
    return TestClient(app).post(f'/api/projects/{project.id}/midi/music', headers={'X-MTA-Request':'1'}, json={
        'publication_id': key or uuid.uuid4().hex, 'expected_revision': expected or revision(project), 'result': data})


def test_sixteen_real_parts_publish_once_and_survive_reopening(workspace):
    data = result()
    data['alternatives'] = [{'id': 'alternative', 'name': 'Alternative instrument', 'notes': [{'pitch': 73}]}]
    key = uuid.uuid4().hex
    response = publish(workspace, data, key)
    assert response.status_code == 200, response.text
    p = storage.load_project(workspace.id)
    assert len(p.tracks) == 16
    assert len({t.name for t in p.tracks}) == 16
    assert [t.midi_notes[0].pitch for t in p.tracks] == list(range(48, 64))
    assert all(t.midi_notes[0].start_ms == 850 and t.music_result_id == key for t in p.tracks)
    assert all(storage.audio_path(p.id, t.filename).is_file() for t in p.tracks)
    assert len(p.music_alternatives) == 1
    assert p.music_alternatives[0].notes[0].start_ms == 750
    assert p.music_alternatives[0].source_result_id == key
    repeated = publish(workspace, data, key)
    assert repeated.status_code == 200 and repeated.json()['replayed']
    assert len(storage.load_project(p.id).tracks) == 16
    data['parts'][0]['notes'][0]['pitch'] = 80
    assert publish(workspace, data, key).status_code == 409


def test_project_edit_prevents_stale_import_and_writes_no_anchor(workspace):
    expected = revision(workspace)
    workspace.bpm = 112.5
    storage.save_project(workspace)
    response = publish(workspace, result(1), expected=expected)
    assert response.status_code == 409
    assert storage.load_project(workspace.id).tracks == []
    assert not list(storage.pdir(workspace.id).joinpath('audio').glob('midi-*'))


def test_storage_failure_leaves_no_partial_project_or_media(workspace, monkeypatch):
    replace = storage.os.replace
    def disk_full(source, target):
        if str(target).endswith('/project.json'):
            raise OSError('disk full')
        return replace(source, target)
    monkeypatch.setattr(storage.os, 'replace', disk_full)
    with pytest.raises(OSError, match='disk full'):
        publish(workspace, result(3))
    assert storage.load_project(workspace.id).tracks == []
    assert not list(storage.pdir(workspace.id).joinpath('audio').glob('midi-*'))


@pytest.mark.parametrize('voices', [4, 8])
def test_harmony_produces_editable_non_crossing_parts_using_confirmed_chords(voices):
    melody = [MidiNote(id=f'n{i}', start_ms=i*500, duration_ms=400, pitch=p) for i, p in enumerate([72, 74, 76, 77])]
    confirmed = Chord(time_ms=0, chord='Cm', manual_override=True)
    estimated = Chord(time_ms=0, chord='C')
    settings = {'voices': voices, 'ranges': [(36+i*3, 72+i*2) for i in range(voices)]}
    output = arrange(melody, [confirmed, estimated], settings)
    assert len(output.parts) == voices
    for index in range(4):
        pitches = [p.notes[index].pitch for p in output.parts]
        assert pitches == sorted(set(pitches))
        assert all(p % 12 in {0, 3, 7} for p in pitches[:-1])
        assert pitches[-1] == melody[index].pitch
    assert all(n.origin == 'generated' and n.confidence is None for p in output.parts for n in p.notes)
    assert MusicResult.model_validate_json(output.model_dump_json()).parts


@pytest.mark.parametrize('data', [{'parts': [{'id': 'empty', 'name': 'Filler'}]},
    {'parts': [{'id': 'p', 'name': 'P', 'notes': [{'id': 'same'}, {'id': 'same'}]}]},
    {'parts': [{'id': 'p', 'name': 'P', 'controls': [{'time_ms': 86400000, 'data': [192, 1]}]}], 'offset_ms': 1}])
def test_invalid_or_filler_music_is_rejected(data):
    with pytest.raises(ValueError):
        MusicResult.model_validate(data)


def test_error_after_atomic_replace_does_not_remove_committed_media(workspace, monkeypatch):
    def fault(path):
        raise OSError('directory flush failed after replacement')
    monkeypatch.setattr(storage, '_fsync_directory', fault)
    data = result(2)
    key = uuid.uuid4().hex
    with pytest.raises(OSError, match='directory flush'):
        publish(workspace, data, key)
    committed = storage.load_project(workspace.id)
    assert len(committed.tracks) == 2
    assert all(storage.audio_path(committed.id,t.filename).is_file() for t in committed.tracks)
    assert publish(workspace, data, key).json()['replayed']


def test_anonymous_cannot_read_revision_or_publish(workspace, monkeypatch):
    monkeypatch.setenv('MTA_ALLOW_INSECURE_NO_AUTH','false')
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER','false')
    client=TestClient(app)
    assert client.get(f'/api/projects/{workspace.id}/midi/revision').status_code == 401
    assert publish(workspace,result(1)).status_code == 401
    assert storage.load_project(workspace.id).tracks == []
