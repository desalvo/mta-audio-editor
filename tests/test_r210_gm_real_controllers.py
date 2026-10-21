"""Actual TinySoundFont PCM acceptance, opt-in licensed external bank required."""
import os
import pytest
import numpy as np

pytestmark=pytest.mark.skipif(not os.getenv('MTA_TEST_GM_RUNTIME'),reason='Requires built core and reviewed FluidR3 GM')


@pytest.fixture
def synth():
    from app.gm_portable import Synth
    instance=Synth({'program':80,'reverb_level':0},48000)
    try:yield instance
    finally:instance.close()


def block(synth,messages=(),duration=.1):
    return synth.process(list(messages),duration=duration,sample_rate=48000)


@pytest.mark.parametrize('controller',[7,11])
def test_real_volume_and_expression_mute_sounding_voices(synth,controller):
    before=block(synth,[([0x90,69,110],0)])
    after=block(synth,[([0xb0,controller,0],0)])
    assert np.max(np.abs(before))>.01 and np.max(np.abs(after))<1e-7


def test_real_velocity_changes_measured_output_energy(synth):
    quiet=block(synth,[([0x90,69,30],0)])
    synth.reset()
    loud=block(synth,[([0x90,69,120],0)])
    assert np.mean(loud*loud)>np.mean(quiet*quiet)*2


def test_real_sustain_keeps_note_after_noteoff_then_releases(synth):
    block(synth,[([0xb0,64,127],0),([0x90,69,110],0),([0x80,69,0],.05)])
    held=block(synth)
    block(synth,[([0xb0,64,0],0)],duration=.5)
    released=block(synth,duration=.2)
    assert np.max(np.abs(held))>.01 and np.mean(released*released)<np.mean(held*held)*.01


def test_real_pan_controller_and_pitchbend(synth):
    block(synth,[([0x90,69,110],0)])
    right=block(synth,[([0xb0,10,127],0)])
    assert np.mean(right[1]*right[1])>np.mean(right[0]*right[0])*1.2
    def peak(wave):
        data=wave.mean(axis=0);spectrum=abs(np.fft.rfft(data*np.hanning(len(data))))
        return np.argmax(spectrum)*48000/len(data)
    center=block(synth,duration=.2)
    bent=block(synth,[([0xe0,127,127],0)],duration=.2)
    ratio=peak(bent)/peak(center)
    assert 1.08<ratio<1.17 # GM default two-semitone pitch range


def test_real_overlapping_notes_and_silence_after_all_sound_off(synth):
    wave=block(synth,[([0x90,69,100],0),([0x90,69,100],.02),([0x90,72,90],.03),([0x80,69,0],.05)])
    assert np.isfinite(wave).all() and np.max(abs(wave[:,3000:]))>.01
    block(synth,[([0xb0,120,0],0)],duration=.1)
    silence=block(synth)
    assert np.max(abs(silence))<1e-6


def test_real_type0_type1_midi_tempo_render(tmp_path):
    import mido
    import soundfile as sf
    from scripts.render_gm_midi import render_file
    for kind in (0,1):
        mid=mido.MidiFile(type=kind,ticks_per_beat=480)
        track=mido.MidiTrack();mid.tracks.append(track)
        track.extend([mido.Message('program_change',channel=0,program=0,time=0),
                      mido.Message('note_on',channel=0,note=60,velocity=100,time=0),
                      mido.MetaMessage('set_tempo',tempo=1000000,time=480),
                      mido.Message('note_off',channel=0,note=60,velocity=0,time=480)])
        if kind==1:
            drums=mido.MidiTrack();drums.extend([mido.Message('note_on',channel=9,note=38,velocity=100,time=480),
                                               mido.Message('note_off',channel=9,note=38,velocity=0,time=60)])
            mid.tracks.append(drums)
        source=tmp_path/f'type-{kind}.mid';destination=source.with_suffix('.wav');mid.save(source)
        report=render_file(source,destination)
        audio,rate=sf.read(destination)
        assert report['seconds']==pytest.approx(2.5) and rate==48000
        assert audio.shape==(120000,2) and np.isfinite(audio).all() and np.max(abs(audio))>.01
