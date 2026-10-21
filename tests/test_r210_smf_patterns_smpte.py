"""Real binary fixtures for independent SMF2 patterns and all SMPTE divisions."""
import io

import mido
import pytest

from app.midi_smf import read_parts, write_parts, division_rate
from app.models import Track, Clip


def source(file_type=2, division=480):
    midi = mido.MidiFile(type=file_type, ticks_per_beat=division)
    for name, tempo in [('Piano', 500000), ('Bass', 1000000)]:
        part = mido.MidiTrack()
        midi.tracks.append(part)
        part.append(mido.MetaMessage('track_name', name=name))
        part.append(mido.MetaMessage('set_tempo', tempo=tempo))
        part.append(mido.Message('note_on', note=60, velocity=100, time=480))
        part.append(mido.Message('note_off', note=60, time=480))
    out = io.BytesIO()
    midi.save(file=out)
    return out.getvalue()


def as_track(part, index):
    return Track(id=f't{index}', name=part['name'], filename=f't{index}.wav', kind='midi',
                 midi_notes=part['notes'], midi_controls=part['controls'], midi_sysex=part['sysex'],
                 midi_meta=part['midi_meta'], midi_smf_type=part['midi_smf_type'],
                 midi_division=part['midi_division'], duration_ms=part['duration_ms'],
                 clips=[Clip(id=f'c{index}', source_end_ms=part['duration_ms'])])


def test_independent_patterns_never_share_tempo():
    parts = read_parts(source())
    assert [p['name'] for p in parts] == ['Piano', 'Bass']
    assert [p['notes'][0].start_ms for p in parts] == [500, 1000]
    assert [p['notes'][0].duration_ms for p in parts] == [500, 1000]
    tracks = [as_track(p, i) for i, p in enumerate(parts)]
    reopened = read_parts(write_parts(tracks, file_type=2))
    assert [p['notes'][0].start_ms for p in reopened] == [500, 1000]
    assert [p['notes'][0].duration_ms for p in reopened] == [500, 1000]


@pytest.mark.parametrize('code, fps', [(-24, 24), (-25, 25), (-29, 30000/1001), (-30, 30)])
def test_smpte_uses_frame_clock_ignoring_tempo(code, fps):
    division = code*256+40
    parts = read_parts(source(2, division))
    expected = 480*1000/(fps*40)
    assert [p['notes'][0].start_ms for p in parts] == pytest.approx([expected, expected])
    tracks = [as_track(p, i) for i, p in enumerate(parts)]
    reopened = read_parts(write_parts(tracks, file_type=2, division=division))
    assert [p['notes'][0].start_ms for p in reopened] == pytest.approx([expected, expected])


@pytest.mark.parametrize('file_type', [0, 1, 2])
def test_export_actual_smf_type_and_note_timing(file_type):
    tracks = [as_track(p, i) for i, p in enumerate(read_parts(source()))]
    binary = write_parts(tracks, file_type=file_type, bpm=112.5, time_signature='7/8')
    assert mido.MidiFile(file=io.BytesIO(binary)).type == file_type
    parts = read_parts(binary)
    starts = sorted(n.start_ms for p in parts for n in p['notes'])
    assert starts == pytest.approx([500, 1000], abs=.6)


@pytest.mark.parametrize('value', [0, -1, -23*256+40, -25*256, True, 32768])
def test_invalid_time_divisions_are_rejected(value):
    with pytest.raises(ValueError):
        division_rate(value)
