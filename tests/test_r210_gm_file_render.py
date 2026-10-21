import numpy as np
import mido
import pytest
from scripts.render_gm_midi import midi_events, render_file


def make_midi(tmp_path):
    midi=mido.MidiFile(ticks_per_beat=480)
    track=mido.MidiTrack()
    midi.tracks.append(track)
    track.extend([mido.Message('program_change',channel=0,program=40,time=0),
                  mido.Message('note_on',channel=0,note=60,velocity=100,time=0),
                  mido.MetaMessage('set_tempo',tempo=1000000,time=480),
                  mido.Message('note_off',channel=0,note=60,velocity=0,time=480)])
    path=tmp_path/'notes.mid';midi.save(path)
    return path


def test_midi_tempo_and_program(tmp_path):
    events,seconds=midi_events(make_midi(tmp_path))
    assert [v[0][0] for v in events]==[0xc0,0x90,0x80]
    assert seconds==pytest.approx(1.5)
    assert events[-1][1]==pytest.approx(1.5)


def test_type2_rejected(tmp_path):
    midi=mido.MidiFile(type=2);midi.tracks.append(mido.MidiTrack())
    path=tmp_path/'bad.mid';midi.save(path)
    with pytest.raises(ValueError,match='type-2'):midi_events(path)


def test_offline_wav_pipeline(tmp_path):
    class MockSynth:
        seen=[]
        def __init__(self,options,rate):self.rate=rate
        def process(self,events,*,duration,sample_rate,num_channels):
            self.seen.extend(events)
            return np.zeros((2,round(duration*sample_rate)),dtype=np.float32)
        def close(self):pass
    path=make_midi(tmp_path)
    result=render_file(path,tmp_path/'out.wav',rate=8000,block_frames=3000,tail=.1,synth_factory=MockSynth)
    import soundfile as sf
    info=sf.info(str(tmp_path/'out.wav'))
    assert result['events']==3 and info.frames==12800
    assert [v[0][0] for v in MockSynth.seen]==[0xc0,0x90,0x80]


def test_rejects_unsupported_sysex(tmp_path):
    midi=mido.MidiFile();track=mido.MidiTrack();midi.tracks.append(track)
    track.append(mido.Message('sysex',data=(1,2,3),time=0))
    path=tmp_path/'sysex.mid';midi.save(path)
    with pytest.raises(ValueError,match='status'):midi_events(path)


def test_failed_gm_export_preserves_existing_wav(tmp_path):
    destination=tmp_path/'original.wav'
    destination.write_bytes(b'preserve previous export')
    class BrokenSynth:
        def __init__(self,options,rate):pass
        def process(self,events,*,duration,sample_rate,num_channels):
            raise RuntimeError('backend failed')
        def close(self):pass
    with pytest.raises(RuntimeError,match='backend failed'):
        render_file(make_midi(tmp_path), destination, rate=8000, synth_factory=BrokenSynth)
    assert destination.read_bytes()==b'preserve previous export'
    assert not list(tmp_path.glob('.mta-gm-*'))

def test_successful_gm_export_replaces_existing_wav(tmp_path):
    destination=tmp_path/'original.wav'
    destination.write_bytes(b'old data')
    class SilentSynth:
        def __init__(self,options,rate):pass
        def process(self,events,*,duration,sample_rate,num_channels):
            return np.zeros((2,round(duration*sample_rate)),dtype=np.float32)
        def close(self):pass
    render_file(make_midi(tmp_path),destination,rate=8000,tail=0,synth_factory=SilentSynth)
    assert destination.read_bytes().startswith(b'RIFF')
    assert not list(tmp_path.glob('.mta-gm-*'))
