import pytest
from pydantic import ValidationError
from app.ai_arranger import RemixRequest, InstrumentSwap, prepare_remix_plan, catalog
from app.models import Project, Track, Chord, Marker


def project():
    return Project(id='demo', title='Demo', bpm=120, tracks=[Track(id='guitar', name='Guitar', type='guitars', filename='g.wav'), Track(id='drum', name='Drums', type='drums', filename='d.wav')], chords=[Chord(time_ms=0, chord='C')], markers=[Marker(time_ms=0, label='Verse')])


def test_auto_remix_uses_prompt_and_preservation():
    p = project()
    result = prepare_remix_plan(p, RemixRequest(mode='auto_remix', preset_id='synthwave', prompt='Deep bass and retro beats'))
    assert result['operation'] == 'remix'
    assert result['musical_context']['chords'][0]['chord'] == 'C'
    assert result['musical_context']['sections'][0]['label'] == 'Verse'
    assert 'Deep bass' in result['prompt']
    assert not result['backend_available']
    assert p.tracks[0].name == 'Guitar'


def test_replace_multiple_instruments():
    result = prepare_remix_plan(project(), RemixRequest(mode='instrument_swap', instrument_swaps=[InstrumentSwap(track_id='guitar', target_instrument='Saxophone'), InstrumentSwap(track_id='drum', target_instrument='Electronic drum kit', preserve_performance=False)]))
    assert len(result['instrument_swaps']) == 2
    assert 'Saxophone' in result['prompt']
    assert 'ONLY' in result['prompt']


@pytest.mark.parametrize('kwargs', [{'mode':'instrument_swap'}, {'mode':'auto_remix','instrument_swaps':[{'track_id':'guitar','target_instrument':'Piano'}]}, {'mode':'instrument_swap','instrument_swaps':[{'track_id':'guitar','target_instrument':'Piano'},{'track_id':'guitar','target_instrument':'Flute'}]}])
def test_invalid_mode(kwargs):
    with pytest.raises(ValidationError):
        RemixRequest(**kwargs)


def test_reject_unknown_track():
    with pytest.raises(ValueError, match='unknown instrument source'):
        prepare_remix_plan(project(), RemixRequest(mode='instrument_swap', instrument_swaps=[InstrumentSwap(track_id='missing', target_instrument='Piano')]))


def test_catalog_remix_not_ready():
    assert 'remix' in catalog()['operations']
    assert not catalog()['generation_available']
