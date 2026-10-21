"""Regression tests for non-scoring paired-audio/MIDI provenance audit."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import mido

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'audit_paired_midi.py'
spec = importlib.util.spec_from_file_location('mta_paired_audit', SCRIPT)
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)


def test_pair_counts_program_changes_and_drum_exclusion(tmp_path, monkeypatch):
    score = mido.MidiFile(type=0, ticks_per_beat=480)
    track = mido.MidiTrack()
    score.tracks.append(track)
    track.append(mido.Message('program_change', channel=0, program=10, time=0))
    track.append(mido.Message('note_on', channel=0, note=60, velocity=90, time=0))
    track.append(mido.Message('note_off', channel=0, note=60, velocity=0, time=480))
    track.append(mido.Message('program_change', channel=0, program=20, time=0))
    track.append(mido.Message('note_on', channel=0, note=62, velocity=90, time=0))
    track.append(mido.Message('note_off', channel=0, note=62, velocity=0, time=480))
    track.append(mido.Message('note_on', channel=9, note=36, velocity=90, time=0))
    track.append(mido.Message('note_off', channel=9, note=36, velocity=0, time=480))
    midi = tmp_path / 'x.mid'
    audio = tmp_path / 'x.wav'
    score.save(midi)
    audio.write_bytes(b'test-audio')
    monkeypatch.setattr(audit_module.subprocess, 'run', lambda *a, **kw: SimpleNamespace(
        stdout=json.dumps({'format': {'duration': '2.0'}, 'streams': []})))
    out = audit_module.audit(midi, audio)
    assert out['midi']['note_on_count'] == 3
    assert out['midi']['distinct_melodic_programs'] == 2
    assert out['midi']['distinct_melodic_channel_program_pairs'] == 2
    assert out['midi']['channels_with_notes'] == 2
    assert out['midi']['unmatched_note_ends'] == 0
    assert out['midi']['dangling_note_starts'] == 0
    assert out['midi']['program_changes']['1'][1]['program'] == 20


def test_refuses_symlink(tmp_path):
    target = tmp_path / 'target'
    target.write_bytes(b'abc')
    link = tmp_path / 'link'
    link.symlink_to(target)
    try:
        audit_module.audit(link, target)
    except ValueError as exc:
        assert 'symlinks' in str(exc)
    else:
        raise AssertionError('Symlink unexpectedly accepted')
