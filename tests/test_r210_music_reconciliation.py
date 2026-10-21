import pytest
from app.music_reconciliation import reconcile
from app.music_interchange import MusicResult,MusicPart
from app.models import MidiNote


def part(name='piano',program=0,times=(0,),pitch=60):
    return MusicPart(id=name,name=name,program=program,source_model=name,
        notes=[MidiNote(id=str(i),pitch=pitch,start_ms=t,duration_ms=200) for i,t in enumerate(times)])


def test_agreement_preserves_originals_and_primary_timing():
    a=MusicResult(parts=[part(times=(0,500))]);b=MusicResult(parts=[part(times=(20,520))])
    result,report=reconcile([('a',a),('b',b)])
    assert len(result.parts)==1 and len(result.parts[0].notes)==2
    assert [n.start_ms for n in result.parts[0].notes]==[0,500]
    assert len(result.alternatives)==2
    assert report['comparisons'][0]['matched_events']==2
    assert report['calibrated_confidence'] is False
    assert a.parts[0].id=='piano'


def test_program_conflict_retains_both_parts():
    result,report=reconcile([('a',MusicResult(parts=[part()])),('b',MusicResult(parts=[part('guitar',24)]))])
    assert len(result.parts)==2
    assert report['comparisons'][0]['instrument_conflicts']==1


def test_repeated_notes_match_one_to_one_without_erasing_polyphony():
    result,report=reconcile([('a',MusicResult(parts=[part()])),('b',MusicResult(parts=[part(times=(0,10))]))])
    assert sum(len(p.notes) for p in result.parts)==2
    assert report['comparisons'][0]['matched_events']==1


def test_unknown_instrument_cannot_collapse_unison_players():
    primary=MusicResult(parts=[part('one',0),part('two',40)])
    result,report=reconcile([('a',primary),('b',MusicResult(parts=[part('unknown',None)]))])
    assert len(result.parts)==3 and report['comparisons'][0]['ambiguous_events']==1


def test_instrument_specific_tolerance_and_offset_validation():
    a=MusicResult(parts=[part()]);b=MusicResult(parts=[part(times=(80,))])
    result,report=reconcile([('a',a),('b',b)],{'instruments':{'0':{'onset_ms':100.}}})
    assert len(result.parts)==1 and report['comparisons'][0]['matched_events']==1
    with pytest.raises(ValueError,match='offset'):reconcile([('a',a),('b',b.model_copy(update={'offset_ms':1}))])
    with pytest.raises(ValueError,match='unique'):reconcile([('a',a),('a',b)])


def test_third_model_does_not_promote_secondary_only_note_to_primary_agreement():
    primary=MusicResult(parts=[part(times=(0,))])
    secondary=MusicResult(parts=[part('second',0,times=(500,))])
    third=MusicResult(parts=[part('third',0,times=(505,))])
    result,report=reconcile([('a',primary),('b',secondary),('c',third)])
    assert [r['matched_events'] for r in report['comparisons']]==[0,0]
    assert sum(len(p.notes) for p in result.parts)==3
    assert len(result.alternatives)==3


def test_same_part_ambiguous_close_repeated_notes_are_not_arbitrarily_matched():
    primary=MusicResult(parts=[part(times=(100, 120))])
    secondary=MusicResult(parts=[part('secondary',times=(110,))])
    result,report=reconcile([('primary',primary),('secondary',secondary)])
    assert report['comparisons'][0]['ambiguous_events']==1
    assert report['comparisons'][0]['matched_events']==0
    assert len(result.parts)==2
    assert report['primary_audit']['notes_without_other_model_support']==2


def test_primary_audit_tracks_independent_support_without_fake_probabilities():
    a=MusicResult(parts=[part(times=(0,500,1000))])
    b=MusicResult(parts=[part('b',times=(5,510))])
    c=MusicResult(parts=[part('c',times=(5,1005))])
    result,report=reconcile([('a',a),('b',b),('c',c)])
    audit=report['primary_audit']
    assert audit['primary_note_count']==3
    assert audit['notes_supported_by_other_model']==3
    assert audit['notes_without_other_model_support']==0
    assert audit['support_distribution']=={'1':2,'2':1}
    assert report['calibrated_confidence'] is False
    assert len(result.alternatives)==3
