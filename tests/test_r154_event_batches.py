"""r154: preflight-atomic event batches and ordered persistent VST3 IPC."""
import struct
from unittest.mock import Mock

import pytest

from native.vst3_probe.stream_worker import (
    EventBlock, MidiEvent, NativeVST3Worker, ParameterPoint,
    prepare_event_batch,
)
from native.vst3_probe.native_chain import NativeChainError


def test_preflight_encodes_sample_aligned_irregular_quanta():
    blocks = [EventBlock([0.1, -0.1] * 8, (MidiEvent('on', 0, 60, 7, 0.8),), ()),
              EventBlock([0.2, -0.2] * 17, (), (ParameterPoint(100, 16, 0.6),))]
    wire = prepare_event_batch(blocks, 2)
    assert [struct.unpack_from('<I', p)[0] for p in wire] == [8, 17]
    assert [struct.unpack_from('<II', p, 4) for p in wire] == [(1, 0), (0, 1)]


def test_invalid_later_block_causes_no_worker_io():
    worker = object.__new__(NativeVST3Worker)
    worker.events_enabled = True
    worker.channels = 2
    worker._exchange = Mock()
    with pytest.raises(ValueError):
        worker.process_event_batch([EventBlock([0.0, 0.0]),
                                    EventBlock([0.0, 0.0], (MidiEvent('on', 0, 60, 1, 0.5),))])
    worker._exchange.assert_not_called()


@pytest.mark.parametrize('blocks', [[], [EventBlock([0.0])] * 129, [None]])
def test_reject_bad_batch_shape(blocks):
    with pytest.raises(ValueError):
        prepare_event_batch(blocks, 2)


def test_preflight_frame_budget():
    with pytest.raises(ValueError):
        prepare_event_batch([EventBlock([0.0] * 512)] * 129, 1)
    assert len(prepare_event_batch([EventBlock([0.0] * 512)] * 128, 1)) == 128


def test_legacy_worker_rejects_events_batch():
    worker = object.__new__(NativeVST3Worker)
    worker.events_enabled = False
    with pytest.raises(ValueError, match='events_enabled'):
        worker.process_event_batch([EventBlock([0.0])])


def test_ordered_batch_and_fault_close():
    import threading
    worker = object.__new__(NativeVST3Worker)
    worker.events_enabled = True
    worker.channels = 1
    worker._lock = threading.Lock()
    worker._closed = False
    worker._proc = Mock()
    worker._proc.poll.return_value = None
    worker.close = Mock()
    seen = []

    def exchange(payload, length):
        frames, = struct.unpack_from('<I', payload)
        seen.append(frames)
        return struct.pack('<I', frames) + struct.pack('<' + 'f' * frames, *([0.25] * frames))

    worker._exchange = exchange
    assert worker.process_event_batch([EventBlock([0.0]), EventBlock([0.0] * 3)]) == [[0.25], [0.25] * 3]
    assert seen == [1, 3]
    worker._exchange = Mock(side_effect=NativeChainError('crashed'))
    with pytest.raises(NativeChainError):
        worker.process_event_batch([EventBlock([0.0])])
    worker.close.assert_called_once_with(force=True)


def test_real_adelay_batch_transport(monkeypatch):
    """Optional real-SDK smoke: stateful IPC, irregular blocks and parameter control."""
    import json
    from pathlib import Path
    import subprocess

    binary = Path('/mnt/data/r153-probe-build/mta_vst3_probe')
    plugin = Path('/mnt/data/r70-adelay-build/VST3/Release/adelay.vst3')
    if not binary.is_file() or not plugin.exists():
        pytest.skip('Steinberg SDK probe and ADelay not present locally')
    from native.vst3_probe.probe import resolve_module_binary
    monkeypatch.setenv('MTA_VST3_PATHS', str(plugin.parent))
    module = resolve_module_binary(plugin)
    metadata = json.loads(subprocess.check_output([str(binary), str(module)], timeout=25))
    cid = next(item['cid'] for item in metadata['classes']
               if item['name'] == 'ADelay' and item['category'] == 'Audio Module Class')
    with NativeVST3Worker((str(plugin), cid), str(binary), channels=2,
                          events_enabled=True, timeout=10) as worker:
        result = worker.process_event_batch([
            EventBlock([0.125, -0.125] * 17),
            EventBlock([0.125, -0.125] * 64,
                       parameters=(ParameterPoint(100, 3, 0.2),)),
            EventBlock([0.125, -0.125] * 128),
        ])
        assert list(map(len, result)) == [34, 128, 256]
        assert all(all(-16 <= value <= 16 for value in block) for block in result)
