"""Regression gates for bounded Vocal Studio and multi-model MIDI subareas."""
import pytest
from app.music_reconciliation import reconcile
from app.music_interchange import MusicPart, MusicResult
from app.models import MidiNote
from app.vocal_synthesis import Settings, validate_voice_lyrics


def _part(identifier, pitch=60, program=0, count=1):
    return MusicPart(id=identifier, name=identifier, program=program,
                     notes=[MidiNote(id=str(i), pitch=pitch, start_ms=i*100,
                                     duration_ms=80) for i in range(count)])


def test_reconciliation_preserves_ambiguous_same_program_unison():
    original=MusicResult(parts=[_part('piano1'),_part('piano2')])
    secondary=MusicResult(parts=[_part('piano3')])
    merged,report=reconcile([('primary',original),('secondary',secondary)])
    assert report['comparisons'][0]['ambiguous_events']==1
    assert sum(len(p.notes) for p in merged.parts)==3
    assert len(merged.alternatives)==3


def test_vocal_aggregate_note_budget_rejected_before_voicebank_load():
    singers=[_part(f'singer{i}',count=6000) for i in range(7)]
    with pytest.raises(ValueError,match='aggregate'):
        validate_voice_lyrics(singers,Settings())
