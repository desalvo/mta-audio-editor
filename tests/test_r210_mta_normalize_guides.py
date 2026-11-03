import subprocess

import numpy as np
import pytest
import soundfile as sf

from app.codec import _mta_normalization_guide, export_mta
from app.models import Clip, MtaSlotMapping, Track
from app.mta_reverse import deobfuscate_media_copy


@pytest.mark.parametrize('target', ['MTA8', 'MTA16'])
@pytest.mark.parametrize('mixed', [False, True])
def test_export_normalizes_musical_bus_without_click_or_chords(tmp_path, monkeypatch, target, mixed):
    import app.storage as storage
    monkeypatch.setattr(storage, 'ROOT', (tmp_path / 'projects').resolve())
    project = storage.create_project('Guides', target=target, owner_user_id=1)
    rate = 44100
    t = np.arange(rate * 2) / rate
    for i, (name, typ, amplitude, frequency) in enumerate([
        ('Music', 'other', .1, 440), ('Metronome', 'click', .4, 1000),
        ('Chords piano', 'keyboards', .3, 1500),
    ]):
        filename = f'{i}.wav'
        samples = amplitude * np.sin(2 * np.pi * frequency * t)
        sf.write(storage.audio_path(project.id, filename), np.column_stack([samples, samples]), rate, subtype='PCM_24')
        project.tracks.append(Track(id=f't{i}', name=name, type=typ, filename=filename, duration_ms=2000,
                                    channels=2, clips=[Clip(id=f'c{i}', source_start_ms=0,
                                    source_end_ms=2000, timeline_start_ms=0)]))
    slots = ([MtaSlotMapping(slot=1, name='mixed', track_ids=['t0', 't1', 't2'])] if mixed else
             [MtaSlotMapping(slot=i + 1, name=str(i), track_ids=[f't{i}']) for i in range(3)])
    output = tmp_path / 'out.mta'
    export_mta(project, output, slots=slots, profile='generic', normalize_peak_db=-12)
    canonical = tmp_path / 'out.mka'
    deobfuscate_media_copy(output, canonical)
    decoded = []
    for i in range(1 if mixed else 3):
        path = tmp_path / f'decoded{i}.wav'
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(canonical), '-map', f'0:a:{i}',
                        '-c:a', 'pcm_f32le', str(path)], check=True)
        decoded.append(sf.read(path)[0][:, 0])

    def magnitude(audio, frequency):
        n = min(len(audio), rate)
        return 2 * abs(np.dot(audio[:n], np.exp(-2j * np.pi * frequency * np.arange(n) / rate))) / n

    assert magnitude(decoded[0], 440) == pytest.approx(10**(-12 / 20), abs=.025)
    assert magnitude(decoded[0 if mixed else 1], 1000) == pytest.approx(.4, abs=.04)
    assert magnitude(decoded[0 if mixed else 2], 1500) == pytest.approx(.3, abs=.04)


def test_guide_detection_uses_existing_generated_convention():
    assert _mta_normalization_guide(Track(id='a', name='renamed', type='other', filename='chords-piano-123.wav'))
    assert _mta_normalization_guide(Track(id='b', name='Accordi', type='other', filename='x.wav'))
    assert not _mta_normalization_guide(Track(id='c', name='Chord guitar', type='guitars', filename='x.wav'))
    assert _mta_normalization_guide(Track(id='d', name='Imported harmony', type='keyboards', filename='x.wav', mta_normalization_exempt=True))


def test_muted_musical_tracks_are_not_amplified_to_target(tmp_path, monkeypatch):
    import app.storage as storage
    monkeypatch.setattr(storage, 'ROOT', (tmp_path / 'projects').resolve())
    project = storage.create_project('Muted', target='MTA16', owner_user_id=1)
    sf.write(storage.audio_path(project.id, 'music.wav'), np.full((4410, 2), .1), 44100)
    project.tracks.append(Track(id='a', name='Muted', filename='music.wav', duration_ms=100,
                                mute=True, clips=[Clip(id='c', source_start_ms=0,
                                source_end_ms=100, timeline_start_ms=0)]))
    with pytest.raises(ValueError, match='silent MTA master'):
        export_mta(project, tmp_path / 'out.mta', profile='generic', normalize_peak_db=-6)


def test_guides_in_mixed_slot_do_not_silently_clip(tmp_path, monkeypatch):
    import app.storage as storage
    monkeypatch.setattr(storage, 'ROOT', (tmp_path / 'projects').resolve())
    project = storage.create_project('Clip', target='MTA16', owner_user_id=1)
    for ident, typ, amplitude in [('music', 'other', .1), ('click', 'click', .4)]:
        filename = ident + '.wav'
        sf.write(storage.audio_path(project.id, filename), np.full((44100, 2), amplitude), 44100)
        project.tracks.append(Track(id=ident, name=ident, type=typ, filename=filename, duration_ms=1000,
            clips=[Clip(id='c' + ident, source_start_ms=0, source_end_ms=1000, timeline_start_ms=0)]))
    slots = [MtaSlotMapping(slot=1, name='both', track_ids=['music', 'click'])]
    with pytest.raises(ValueError, match='guide would clip'):
        export_mta(project, tmp_path / 'out.mta', slots=slots, profile='generic', normalize_peak_db=-1)
