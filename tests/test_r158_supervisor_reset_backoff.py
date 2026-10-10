"""r158: control-thread recovery spacing and explicit seek barriers."""
from unittest.mock import Mock

import pytest

from native.vst3_probe.native_chain import NativeChainError
from native.vst3_probe.stream_worker import EventBlock
from native.vst3_probe.supervised_worker import SupervisedVST3Worker


def make_worker(*, failure=False):
    worker = Mock(channels=2, events_enabled=True)
    if failure:
        worker.process_event_batch.side_effect = NativeChainError('plugin crashed')
    else:
        worker.process_event_batch.return_value = [[0.3, -0.3]]
    return worker


def test_deferred_recovery_never_replays_failed_or_gap_blocks():
    first, second = make_worker(failure=True), make_worker()
    factory = Mock(side_effect=[first, second])
    s = SupervisedVST3Worker(factory, max_restarts=1, recovery_gap_blocks=3)
    quantum = EventBlock([0.1, -0.1])
    assert s.process(quantum) == [0.1, -0.1]
    for _ in range(3):
        assert s.process(quantum) == [0.1, -0.1]
    assert factory.call_count == 1
    assert s.stats.deferred_blocks == 3 and s.stats.dry_blocks == 4
    assert s.process(quantum) == [0.3, -0.3]
    assert s.stats.restarts == 1 and s.stats.epoch == 2
    first.process_event_batch.assert_called_once()
    second.process_event_batch.assert_called_once()
    s.close()


def test_seek_releases_old_worker_without_reusing_plugin_state():
    first, second = make_worker(), make_worker()
    factory = Mock(side_effect=[first, second])
    s = SupervisedVST3Worker(factory, max_restarts=0)
    block = EventBlock([0.0, 0.0])
    assert s.process(block) == [0.3, -0.3]
    s.reset_session()
    first.close.assert_called_once_with(force=True)
    assert s.process(block) == [0.3, -0.3]
    assert s.stats.epoch == 2 and s.stats.resets == 1
    assert s.stats.restarts == 0
    s.close()


def test_seek_recovers_from_exhausted_restart_budget():
    failed, good = make_worker(failure=True), make_worker()
    s = SupervisedVST3Worker(Mock(side_effect=[failed, good]), max_restarts=0, recovery_gap_blocks=10)
    block = EventBlock([0.1, 0.2])
    assert s.process(block) == [0.1, 0.2]
    assert s.stats.disabled
    s.reset_session()
    assert not s.stats.disabled
    assert s.process(block) == [0.3, -0.3]
    s.close()
    with pytest.raises(RuntimeError):
        s.reset_session()


@pytest.mark.parametrize('gap', [-1, True, 4097, 1.5])
def test_reject_bad_recovery_gap(gap):
    with pytest.raises(ValueError):
        SupervisedVST3Worker(lambda: make_worker(), recovery_gap_blocks=gap)
