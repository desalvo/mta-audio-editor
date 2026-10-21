import pytest
from app.gm_instruments import validate_midi_packet, schedule_gm_events

@pytest.mark.parametrize('message', [
    bytes([0x90, 60, 100]), [0x80, 60, 0], [0xC1, 127], [0xD1, 10],
    [0xE0, 0, 127], [0xB9, 64, 127], [0xF0, 126, 127, 9, 1, 247],
])
def test_valid_message(message):
    assert tuple(message) == validate_midi_packet(message)

@pytest.mark.parametrize('message', [
    [], [0x90, 60], [0x90, 60, 128], [0x90, -1, 1], [0x90, True, 1],
    [0xC0, 1, 2], [0xF0, 1, 247], [0xF8], [0x90, 60, 100, 0], [0x90, 60, 1.0],
])
def test_invalid_message(message):
    with pytest.raises(ValueError):
        validate_midi_packet(message)

def test_schedule_preserves_same_timestamp_order():
    a = bytes([0x80,60,0]);b = bytes([0x90,60,90]);c = bytes([0xB0,64,0])
    assert schedule_gm_events([(c,.2),(a,.1),(b,.1)],duration=.3,rate=48000)==[(tuple(a),.1),(tuple(b),.1),(tuple(c),.2)]

@pytest.mark.parametrize('seconds',[-.01,.51,float('nan'),float('inf')])
def test_schedule_rejects_outside_event(seconds):
    with pytest.raises(ValueError):
        schedule_gm_events([([0x90,60,100],seconds)],duration=.5,rate=48000)

def test_schedule_rejects_excessive_events():
    with pytest.raises(ValueError,match='Too many'):
        schedule_gm_events([([0x90,60,100],0)]*20001,duration=.5,rate=48000)


def test_reject_unreasonable_gm_sampling_frequency():
    import pytest
    from app.gm_instruments import schedule_gm_events
    with pytest.raises(ValueError, match="sample rate"):
        schedule_gm_events([], duration=0.1, rate=0)


def test_portable_gm_closed_configuration_refused_without_native_calls():
    from app.gm_portable import Synth
    instrument = object.__new__(Synth)
    instrument.handle = None
    with pytest.raises(RuntimeError, match='closed'):
        instrument.configure({})
