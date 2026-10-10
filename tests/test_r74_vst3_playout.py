"""Non-realtime deadline, fault and safety tests for the VST3 playout coordinator."""
import pytest
from types import SimpleNamespace
from native.vst3_probe.playout import PlayoutCoordinator


class FakeBridge:
    def __init__(self):
        self.requests = []
        self.results = []
        self.fault = None
        self.next_seq = 0
        self.allow = True

    def submit(self, samples):
        if not self.allow:
            return None
        seq = self.next_seq
        self.next_seq += 1
        self.requests.append((seq, tuple(samples)))
        return seq

    def poll(self):
        return self.results.pop(0) if self.results else None

    def close(self):
        return True


def test_wet_processing_arrives_before_deadline():
    bridge = FakeBridge()
    c = PlayoutCoordinator(bridge, channels=1, lookahead_blocks=2)
    assert c.submit([.1, .2]) == 0
    assert c.advance() == []
    bridge.results.append(SimpleNamespace(sequence=0, samples=(.5, .6), error=None))
    assert c.advance()[0].samples == (.5, .6)
    assert c.stats.processed == 1


def test_missed_deadline_bypasses_and_late_pcm_is_discarded():
    bridge = FakeBridge()
    c = PlayoutCoordinator(bridge, channels=1, lookahead_blocks=1)
    assert c.submit([.2]) == 0
    assert c.advance()[0].status == 'bypass'
    bridge.results.append(SimpleNamespace(sequence=0, samples=(.9,), error=None))
    assert c.advance() == []
    assert c.stats.discarded_late == 1


def test_fault_falls_back_without_replaying():
    bridge = FakeBridge()
    c = PlayoutCoordinator(bridge, channels=1, lookahead_blocks=1)
    c.submit([.3])
    bridge.results.append(SimpleNamespace(sequence=0, samples=(), error='plugin crashed'))
    assert c.advance()[0].samples == (.3,)
    assert c.stats.faulted
    assert c.submit([.4]) is None


def test_capacity_and_rejections():
    bridge = FakeBridge()
    c = PlayoutCoordinator(bridge, channels=1, lookahead_blocks=2, max_pending=2)
    c.submit([.1]); c.submit([.2])
    assert c.submit([.3]) is None
    assert c.stats.rejected == 1
    assert len(c.flush_dry()) == 2
    assert c.close()


def test_stereo_preserved_and_sorted():
    bridge = FakeBridge()
    c = PlayoutCoordinator(bridge, lookahead_blocks=1)
    c.submit([.1, -.1]); c.submit([.2, -.2])
    bridge.results.extend([
        SimpleNamespace(sequence=1, samples=(.7, -.7), error=None),
        SimpleNamespace(sequence=0, samples=(.6, -.6), error=None),
    ])
    out = c.advance()
    assert [x.sequence for x in out] == [0, 1]
    assert [x.samples for x in out] == [(.6, -.6), (.7, -.7)]


@pytest.mark.parametrize('kwargs', [dict(channels=3), dict(lookahead_blocks=0),
    dict(lookahead_blocks=33), dict(max_pending=0), dict(max_pending=257),
    dict(lookahead_blocks=True)])
def test_invalid_configuration(kwargs):
    with pytest.raises(ValueError):
        PlayoutCoordinator(FakeBridge(), **kwargs)


@pytest.mark.parametrize('block', [[], [float('nan')], [float('inf')], [17.0], [True], [1]*513])
def test_invalid_samples(block):
    with pytest.raises(ValueError):
        PlayoutCoordinator(FakeBridge(), channels=1).submit(block)
