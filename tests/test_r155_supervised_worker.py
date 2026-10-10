"""r155: bounded worker recovery and no hidden partial-batch replay."""
from unittest.mock import Mock

import pytest

from native.vst3_probe.native_chain import NativeChainError
from native.vst3_probe.stream_worker import EventBlock, MidiEvent
from native.vst3_probe.supervised_worker import SupervisedVST3Worker


def fake_worker(side_effect=None):
    worker = Mock()
    worker.channels = 2
    worker.events_enabled = True
    if side_effect is None:
        worker.process_event_batch.side_effect = lambda blocks: [[0.25] * len(blocks[0].pcm)]
    else:
        worker.process_event_batch.side_effect = side_effect
    return worker


def test_success_keeps_one_plugin_instance():
    factory = Mock(side_effect=lambda: fake_worker())
    s = SupervisedVST3Worker(factory)
    assert s.process(EventBlock([0.4, 0.5])) == [0.25, 0.25]
    assert s.process(EventBlock([0.4, 0.5])) == [0.25, 0.25]
    assert s.stats.epoch == 1 and s.stats.processed_blocks == 2
    factory.assert_called_once()
    s.close()


def test_fault_uses_dry_without_replay_and_recovers_next_quantum():
    first = fake_worker(NativeChainError('broken IPC'))
    second = fake_worker()
    factory = Mock(side_effect=[first, second])
    s = SupervisedVST3Worker(factory, max_restarts=1)
    block = EventBlock([0.4, 0.5])
    assert s.process(block) == [0.4, 0.5]
    assert s.stats.epoch == 1 and s.stats.faults == 1
    first.process_event_batch.assert_called_once()
    assert s.process(block) == [0.25, 0.25]
    assert s.stats.epoch == 2 and s.stats.restarts == 1
    second.process_event_batch.assert_called_once()
    s.close()


def test_restart_budget_exhaustion_disables_worker():
    factory = Mock(side_effect=lambda: fake_worker(NativeChainError('fault')))
    s = SupervisedVST3Worker(factory, max_restarts=2)
    for _ in range(12):
        assert s.process(EventBlock([0.0, 1.0])) == [0.0, 1.0]
    assert factory.call_count == 3
    assert s.stats.disabled and s.stats.faults == 3 and s.stats.dry_blocks == 12
    s.close()


def test_factory_failure_budget_is_bounded():
    factory = Mock(side_effect=OSError('no plugin'))
    s = SupervisedVST3Worker(factory, max_restarts=1)
    for _ in range(4):
        assert s.process(EventBlock([0.0, 0.0])) == [0.0, 0.0]
    assert factory.call_count == 2 and s.stats.disabled


def test_shape_and_nonfinite_output_trigger_dry_fallback():
    s = SupervisedVST3Worker(lambda: fake_worker(), max_restarts=0)
    s._factory = lambda: fake_worker()
    bad = fake_worker()
    bad.process_event_batch.return_value = [[float('nan'), 0.0]]
    bad.process_event_batch.side_effect = None
    s._factory = lambda: bad
    assert s.process(EventBlock([0.1, 0.2])) == [0.1, 0.2]
    assert s.stats.disabled


def test_invalid_event_rejected_before_plugin_creation():
    factory = Mock(side_effect=lambda: fake_worker())
    s = SupervisedVST3Worker(factory)
    with pytest.raises(ValueError):
        s.process(EventBlock([0.0, 0.0], (MidiEvent('on', 0, 60, 100, 0.5),)))
    factory.assert_not_called()


def test_close_prevents_future_restarts():
    factory = Mock(side_effect=lambda: fake_worker())
    s = SupervisedVST3Worker(factory)
    s.close()
    assert s.process(EventBlock([0.1, -0.1])) == [0.1, -0.1]
    factory.assert_not_called()


@pytest.mark.parametrize('channels,max_restarts', [(0, 1), (2, -1), (2, 33), (True, 1)])
def test_bad_configurations(channels, max_restarts):
    with pytest.raises(ValueError):
        SupervisedVST3Worker(lambda: fake_worker(), channels=channels, max_restarts=max_restarts)
