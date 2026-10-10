"""Bounded MIDI and parameter IPC, opt-in compatibility and real SDK smoke."""
import json
from pathlib import Path
import struct
import subprocess

import pytest

from native.vst3_probe import stream_worker as sw


ROOT = Path(__file__).resolve().parents[1]


def test_wire_layout_and_sample_offsets():
    midi = [sw.MidiEvent('on', 2, 64, 12, 0.6, 7), sw.MidiEvent('off', 2, 64, 31, 0.0, 7)]
    points = [sw.ParameterPoint(901, 8, 0.25)]
    packed = sw._encode_events(midi, points, 32)
    assert len(packed) == 8 + 2 * 12 + 12
    assert struct.unpack_from('<II', packed) == (2, 1)
    assert struct.unpack_from('<BBBBHHf', packed, 8) == pytest.approx((1, 2, 64, 0, 12, 7, 0.6))
    assert struct.unpack_from('<IHHf', packed, 32) == (901, 8, 0, 0.25)


@pytest.mark.parametrize('event', [
    sw.MidiEvent('on', 16, 60, 0, 0.5),
    sw.MidiEvent('on', 0, 128, 0, 0.5),
    sw.MidiEvent('on', 0, 60, 32, 0.5),
    sw.MidiEvent('on', 0, 60, 0, float('nan')),
    sw.MidiEvent('on', 0, 60, 0, 0.5, -1),
    sw.MidiEvent('bad', 0, 60, 0, 0.5),
])
def test_reject_bad_midi(event):
    with pytest.raises(ValueError):
        sw._encode_events([event], [], 32)


@pytest.mark.parametrize('point', [
    sw.ParameterPoint(-1, 0, 0.5),
    sw.ParameterPoint(17, -1, 0.5),
    sw.ParameterPoint(17, 32, 0.5),
    sw.ParameterPoint(17, 0, float('inf')),
    sw.ParameterPoint(17, 0, 1.1),
    sw.ParameterPoint(2**32, 0, 0.5),
])
def test_reject_bad_automation(point):
    with pytest.raises(ValueError):
        sw._encode_events([], [point], 32)


def test_envelope_limits_and_legacy_mode():
    with pytest.raises(ValueError):
        sw._encode_events([sw.MidiEvent('on', 0, 60, 0, 0.5)] * 33, [], 32)
    with pytest.raises(ValueError):
        sw._encode_events([], [sw.ParameterPoint(2, 0, 0.5)] * 33, 32)
    assert len(sw._encode_events([], [], 32)) == 8
    assert sw._encode_block([0.2] * 32, 1)[:4] == struct.pack('<I', 32)


def test_sdk_dispatch_mode_and_readiness_guard():
    code = (ROOT / 'native/vst3_probe/main.cpp').read_text()
    assert '--stream-events' in code
    assert 'parameterChanges.addParameterData(item.id, queueIndex)' in code
    assert 'events.addEvent(event)' in code
    assert 'native_host_ready\\":false' in code


def test_real_adelay_offline_event_transport(monkeypatch):
    binary = Path('/mnt/data/r153-probe-build/mta_vst3_probe')
    plugin = Path('/mnt/data/r70-adelay-build/VST3/Release/adelay.vst3')
    if not binary.is_file() or not plugin.exists():
        pytest.skip('Optional locally compiled Steinberg SDK and ADelay')
    monkeypatch.setenv('MTA_VST3_PATHS', str(plugin.parent))
    from native.vst3_probe.probe import resolve_module_binary
    metadata = json.loads(subprocess.check_output([str(binary), str(resolve_module_binary(plugin))], timeout=25))
    cid = next(x['cid'] for x in metadata['classes'] if x['name'] == 'ADelay' and x['category'] == 'Audio Module Class')
    with sw.NativeVST3Worker((str(plugin), cid), str(binary), channels=2,
                             events_enabled=True, timeout=10) as worker:
        # Empty events preserve audio parity and transport state.
        a = worker.process([0.125, -0.125] * 128)
        b = worker.process_with_events([0.125, -0.125] * 17)
        assert len(a) == 256 and len(b) == 34
        # ADelay exposes parameter 100 (delay time) and accepts automated values.
        automated = worker.process_with_events([0.125, -0.125] * 64,
                                               parameters=[sw.ParameterPoint(100, 3, 0.2)])
        assert len(automated) == 128
        # Invalid parameter IDs are rejected by SDK-side worker: no silently lost automation.
        with pytest.raises(sw.NativeChainError):
            worker.process_with_events([0.0, 0.0] * 32, parameters=[sw.ParameterPoint(0xffffffff, 4, 0.5)])
