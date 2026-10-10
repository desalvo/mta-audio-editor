"""r162: corrupted or extreme PCM never escapes the isolated VST3 worker."""
import struct

import pytest

from native.vst3_probe.native_chain import NativeChainError
from native.vst3_probe.stream_worker import EventBlock, _decode_block
from native.vst3_probe.supervised_worker import SupervisedVST3Worker


@pytest.mark.parametrize('sample', [17.0, -20.0, float('nan'), float('inf')])
def test_transport_rejects_extreme_pcm(sample):
    with pytest.raises(NativeChainError):
        _decode_block(struct.pack('<Iff', 1, sample, 0.0), 1, 2)


class FakeWorker:
    channels = 2
    events_enabled = True

    def __init__(self, value):
        self.value = value
        self.closed = False

    def process_event_batch(self, blocks):
        return [[self.value] * len(blocks[0].pcm)]

    def close(self, *, force=False):
        self.closed = True


@pytest.mark.parametrize('sample', [17.0, -20.0, float('nan'), float('inf'), 'bad', True])
def test_supervisor_containment_on_bad_adapter_pcm(sample):
    created = []

    def factory():
        worker = FakeWorker(sample)
        created.append(worker)
        return worker

    supervisor = SupervisedVST3Worker(factory, max_restarts=1)
    block = EventBlock([0.25, -0.25] * 8)
    assert supervisor.process(block) == list(block.pcm)
    assert created[0].closed
    assert supervisor.stats.faults == 1
    assert supervisor.stats.dry_blocks == 1
    supervisor.close()
