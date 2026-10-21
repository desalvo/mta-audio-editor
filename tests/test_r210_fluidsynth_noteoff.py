"""Idempotent release is required for short samples and stolen MIDI voices."""
from types import SimpleNamespace
import pytest
from app.gm_instruments import FluidSynth


@pytest.mark.parametrize('packet',[[0x80,60,0],[0x90,60,0],[0x89,75,0]])
def test_completed_voice_noteoff_does_not_abort_render(packet):
    calls=[]
    synth=FluidSynth.__new__(FluidSynth)
    synth.synth=1;synth.settings=None
    synth.lib=SimpleNamespace(fluid_synth_noteoff=lambda *args:calls.append(args) or -1)
    try:
        synth.message(packet)
        assert calls==[(1,packet[0]&15,60 if packet[0]&15==0 else 75)]
    finally:synth.synth=None


def test_other_midi_errors_remain_fatal():
    synth=FluidSynth.__new__(FluidSynth);synth.synth=1;synth.settings=None
    synth.lib=SimpleNamespace(fluid_synth_noteon=lambda *args:-1)
    try:
        with pytest.raises(ValueError,match='noteon'):synth.message([0x90,60,100])
    finally:synth.synth=None
