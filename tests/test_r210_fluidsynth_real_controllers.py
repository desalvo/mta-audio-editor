"""Actual FluidSynth controller/PCM checks, opt-in reviewed external bank."""
import ctypes as C
import os
import numpy as np
import pytest

pytestmark=pytest.mark.skipif(not os.getenv('MTA_TEST_FLUIDSYNTH'),reason='Requires reviewed FluidSynth shared library and FluidR3')


@pytest.fixture
def synth():
    from app.gm_instruments import FluidSynth
    value=FluidSynth({'program':80,'reverb_level':0},48000)
    for effect in ('chorus','reverb'):
        function=getattr(value.lib,'fluid_synth_set_'+effect+'_on')
        function.argtypes=[C.c_void_p,C.c_int,C.c_int];function.restype=C.c_int
        function(value.synth,-1,0)
    try:yield value
    finally:value.close()


def block(synth,messages=(),duration=.2):return synth.process(list(messages),duration=duration,sample_rate=48000)


@pytest.mark.parametrize('cc',[7,11])
def test_volume_expression_mute_real_sustained_audio(synth,cc):
    before=block(synth,[([0x90,69,110],0)])
    block(synth,[([0xb0,cc,0],0)])
    after=block(synth)
    assert np.mean(before*before)>1e-5
    assert np.mean(after*after)<np.mean(before*before)*1e-4


def test_velocity_and_pitch_bend_have_measurable_effect(synth):
    quiet=block(synth,[([0x90,69,30],0)]);synth.reset()
    loud=block(synth,[([0x90,69,120],0)])
    assert np.mean(loud*loud)>2*np.mean(quiet*quiet)
    center=block(synth);block(synth,[([0xe0,127,127],0)]);bent=block(synth)
    def peak(w):return np.argmax(abs(np.fft.rfft(w.mean(axis=0)*np.hanning(w.shape[1]))))
    assert 1.08<peak(bent)/peak(center)<1.17


def test_pan_sustain_polyphony_and_reset(synth):
    block(synth,[([0xb0,10,127],0),([0xb0,64,127],0),([0x90,69,110],0),([0x80,69,0],.05)])
    held=block(synth)
    block(synth,[([0xb0,10,0],0)]);left=block(synth)
    # SF2 presets may already contain stereo/pan modulators. Compare the
    # actual same-preset response to opposite controller positions.
    right_ratio=np.mean(held[1]*held[1])/np.mean(held[0]*held[0])
    left_ratio=np.mean(left[1]*left[1])/np.mean(left[0]*left[0])
    assert right_ratio>left_ratio*1.1
    block(synth,[([0xb0,64,0],0)],duration=.5);release=block(synth)
    assert np.mean(release*release)<.01*np.mean(held*held)
    voices=block(synth,[([0x90,p,100],0) for p in range(48,80)])
    assert np.isfinite(voices).all() and np.max(abs(voices))>.01
    synth.reset();silence=block(synth)
    assert np.max(abs(silence))<1e-5
