"""r160: safe control-thread initialization of every isolated worker epoch."""
from unittest.mock import Mock

import pytest

from native.vst3_probe.stream_worker import EventBlock
from native.vst3_probe.supervised_worker import SupervisedVST3Worker


def worker(result=None, error=None):
    w = Mock(channels=2, events_enabled=True)
    w.process_event_batch.return_value = [[0.6, 0.7]] if result is None else result
    if error is not None:
        w.process_event_batch.side_effect = error
    return w


def test_initial_state_is_restored_before_any_pcm():
    w = worker()
    calls = []
    def restore(instance):
        assert instance is w
        calls.append('restore')
        instance.process_event_batch.side_effect = lambda _: calls.append('pcm') or [[0.6, 0.7]]
    s = SupervisedVST3Worker(lambda: w, restore_state=restore)
    assert s.process(EventBlock([0.1, 0.2])) == [0.6, 0.7]
    assert calls == ['restore', 'pcm']
    assert s.stats.restored_sessions == 1
    s.close()


def test_fault_reopens_and_restores_new_instance_without_replaying_faulted_block():
    failed = worker(error=OSError('IPC broke'))
    replacement = worker()
    restored = []
    s = SupervisedVST3Worker(Mock(side_effect=[failed, replacement]),
                             max_restarts=1, restore_state=lambda w: restored.append(w))
    block = EventBlock([0.2, 0.3])
    assert s.process(block) == [0.2, 0.3]
    assert restored == [failed]
    assert s.process(block) == [0.6, 0.7]
    assert restored == [failed, replacement]
    assert s.stats.restored_sessions == 2
    failed.process_event_batch.assert_called_once()
    s.close()


def test_restore_failure_discards_child_and_returns_dry_with_bounded_retries():
    a, b = worker(), worker()
    def restore(w):
        raise RuntimeError('corrupt state')
    factory = Mock(side_effect=[a, b])
    s = SupervisedVST3Worker(factory, max_restarts=1, restore_state=restore)
    for _ in range(4):
        assert s.process(EventBlock([0.2, -0.2])) == [0.2, -0.2]
    a.close.assert_called_once_with(force=True)
    b.close.assert_called_once_with(force=True)
    assert factory.call_count == 2
    assert s.stats.restore_failures == 2
    assert s.stats.disabled
    s.close()


def test_reset_recreates_and_restores_fresh_epoch():
    a, b = worker(), worker()
    factory = Mock(side_effect=[a, b])
    restored = []
    s = SupervisedVST3Worker(factory, restore_state=lambda w: restored.append(w))
    s.process(EventBlock([0.1, 0.2]))
    s.reset_session()
    s.process(EventBlock([0.3, 0.4]))
    assert restored == [a, b]
    assert s.stats.epoch == 2 and s.stats.resets == 1
    a.close.assert_called_once_with(force=True)
    s.close()


def test_restore_callback_is_optional_and_validated():
    with pytest.raises(ValueError):
        SupervisedVST3Worker(lambda: worker(), restore_state=True)
    s = SupervisedVST3Worker(lambda: worker())
    assert s.process(EventBlock([0.1, 0.2])) == [0.6, 0.7]
    assert s.stats.restored_sessions == 0
    s.close()
