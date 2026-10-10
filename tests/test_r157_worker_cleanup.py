"""Regression: rejected worker startups must not leak isolated VST3 processes."""
from unittest.mock import Mock

from native.vst3_probe.stream_worker import EventBlock
from native.vst3_probe.supervised_worker import SupervisedVST3Worker


def test_rejected_channel_worker_is_force_closed_before_recovery():
    wrong = Mock(channels=1, events_enabled=True)
    good = Mock(channels=2, events_enabled=True)
    good.process_event_batch.return_value = [[0.25, 0.5]]
    factory = Mock(side_effect=[wrong, good])
    supervisor = SupervisedVST3Worker(factory, max_restarts=1)
    block = EventBlock([0.0, 0.0])
    assert supervisor.process(block) == [0.0, 0.0]
    wrong.close.assert_called_once_with(force=True)
    assert supervisor.stats.faults == 1
    assert supervisor.process(block) == [0.25, 0.5]
    assert supervisor.stats.restarts == 1
    supervisor.close()
    good.close.assert_called_once_with(force=True)


def test_rejected_event_protocol_worker_is_force_closed():
    worker = Mock(channels=2, events_enabled=False)
    supervisor = SupervisedVST3Worker(lambda: worker, max_restarts=0)
    assert supervisor.process(EventBlock([0.1, -0.1])) == [0.1, -0.1]
    worker.close.assert_called_once_with(force=True)
    assert supervisor.stats.disabled


def test_close_failure_does_not_mask_factory_validation_fault():
    worker = Mock(channels=1, events_enabled=True)
    worker.close.side_effect = OSError('subprocess already gone')
    supervisor = SupervisedVST3Worker(lambda: worker, max_restarts=0)
    assert supervisor.process(EventBlock([0.1, 0.2])) == [0.1, 0.2]
    assert supervisor.stats.faults == 1 and supervisor.stats.disabled
