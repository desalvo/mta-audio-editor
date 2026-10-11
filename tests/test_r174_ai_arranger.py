import pytest
from pydantic import ValidationError
from app.ai_arranger import RearrangeRequest, prepare_plan, catalog
from app.models import Project, Marker, Chord, Track


def example_project():
    return Project(id='sample', title='Demo', bpm=108, time_signature='6/8', key='Am',
                   markers=[Marker(time_ms=1000, label='Verse'), Marker(time_ms=5000, label='Chorus', disabled=True)],
                   chords=[Chord(time_ms=1000, chord='Am'), Chord(time_ms=2000, chord='F', excluded=True)],
                   tracks=[Track(id='bass', name='Bass', filename='bass.wav')])


def test_arranger_catalog_not_yet_available():
    data = catalog()
    assert not data['generation_available']
    assert not data['native_host_ready']
    assert {'ace-step-1.5', 'diffrhythm-2'} == {entry['id'] for entry in data['models']}


def test_arranger_preserves_metadata_when_requested():
    req = RearrangeRequest(preserve_chords=True, preserve_structure=True)
    p = example_project()
    plan = prepare_plan(p, req)
    assert plan['musical_context']['chords'] == [{'time_ms': 1000, 'end_ms': None, 'chord': 'Am'}]
    assert plan['musical_context']['sections'] == [{'time_ms': 1000, 'end_ms': None, 'label': 'Verse'}]
    assert plan['musical_context']['meter'] == '6/8'
    assert plan['guarantees']['chords'] is False
    assert p.chords[0].chord == 'Am'


def test_arranger_no_constraints_when_disabled():
    plan = prepare_plan(example_project(), RearrangeRequest(preserve_chords=False, preserve_structure=False))
    assert not plan['musical_context']['chords']
    assert not plan['musical_context']['sections']


def test_arranger_selected_tracks_validated():
    with pytest.raises(ValueError, match='unknown track'):
        prepare_plan(example_project(), RearrangeRequest(scope='tracks', track_ids=['missing']))
    assert prepare_plan(example_project(), RearrangeRequest(scope='tracks', track_ids=['bass']))['track_ids'] == ['bass']


@pytest.mark.parametrize('kwargs', [
    {'scope': 'range', 'start_ms': 100, 'end_ms': 100},
    {'scope': 'tracks'},
    {'scope': 'project', 'track_ids': ['bass']},
    {'preset_id': 'unknown'},
    {'scope': 'range', 'start_ms': 20, 'end_ms': 10},
    {'strength': 101},
])
def test_arranger_invalid_requests(kwargs):
    with pytest.raises(ValidationError):
        RearrangeRequest(**kwargs)
