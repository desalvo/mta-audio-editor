"""r72 regression: bounded asynchronous VST3 output ordering and dry bypass."""
from dataclasses import dataclass
import pytest

from native.vst3_probe.ordered_bridge import OrderedBridgeAdapter


@dataclass
class Result:
    sequence: int
    samples: tuple[float, ...]
    error: str | None = None


class FakeBridge:
    def __init__(self):
        self.next = 0
        self.queue = []
        self.fault = None
    def submit(self, samples):
        seq = self.next
        self.next += 1
        return seq
    def poll(self):
        return self.queue.pop(0) if self.queue else None
    def close(self):
        return True


def test_processed_output():
    bridge = FakeBridge()
    adapter = OrderedBridgeAdapter(bridge)
    assert adapter.submit([.1, -.1]) == 0
    bridge.queue.append(Result(0, (.2, -.2)))
    delivered = adapter.deliver()
    assert delivered.status == 'processed'
    assert delivered.samples == (.2, -.2)


def test_late_result_never_shifts_audio_forward():
    bridge = FakeBridge()
    adapter = OrderedBridgeAdapter(bridge)
    adapter.submit([.1, -.1])
    adapter.submit([.3, -.3])
    assert adapter.deliver().status == 'bypass'
    bridge.queue.extend([Result(0, (9., 9.)), Result(1, (.4, -.4))])
    delivered = adapter.deliver()
    assert delivered.sequence == 1
    assert delivered.samples == (.4, -.4)
    assert adapter.deliver() is None


def test_backpressure_and_recovery():
    bridge = FakeBridge()
    adapter = OrderedBridgeAdapter(bridge, max_pending=1)
    assert adapter.submit([.2, -.2]) == 0
    assert adapter.submit([.3, -.3]) is None
    assert adapter.deliver().status == 'bypass'
    assert adapter.submit([.3, -.3]) == 1


def test_worker_error_dry_bypass():
    bridge = FakeBridge()
    adapter = OrderedBridgeAdapter(bridge)
    adapter.submit([.2, -.2])
    bridge.queue.append(Result(0, (), 'worker terminated'))
    assert adapter.deliver().status == 'bypass'
    assert adapter.fault == 'worker terminated'
    assert adapter.submit([.2, -.2]) is None


def test_bad_processed_length_bypasses():
    bridge = FakeBridge()
    adapter = OrderedBridgeAdapter(bridge)
    adapter.submit([.2, -.2])
    bridge.queue.append(Result(0, (.4,)))
    assert adapter.deliver().status == 'bypass'
    assert adapter.fault == 'Invalid processed PCM block'


@pytest.mark.parametrize('channels,samples', [(2, [1.]), (1, [float('nan')]), (1, [True])])
def test_input_validation(channels, samples):
    bridge = FakeBridge()
    adapter = OrderedBridgeAdapter(bridge, channels=channels)
    with pytest.raises(ValueError):
        adapter.submit(samples)
