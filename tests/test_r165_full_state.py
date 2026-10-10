"""r165: component/controller state consistency under supervised recovery."""
from unittest.mock import Mock

import pytest

from native.vst3_probe.stream_worker import EventBlock
from native.vst3_probe.supervised_worker import SupervisedVST3Worker


BLOCK = EventBlock([0.1, -0.2])


def _worker():
    w = Mock(channels=2, events_enabled=True)
    w.process_event_batch.return_value = [[0.3, -0.4]]
    w.snapshot_state.return_value = b'processor'
    w.snapshot_controller_state.return_value = b'controller'
    return w


def test_joint_snapshot_restores_in_order_after_seek():
    a, b = _worker(), _worker()
    supervisor = SupervisedVST3Worker(Mock(side_effect=[a, b]), max_restarts=1)
    assert supervisor.process(BLOCK) == [0.3, -0.4]
    assert supervisor.checkpoint_full_state() == (b'processor', b'controller')
    supervisor.reset_session()
    assert supervisor.process(BLOCK) == [0.3, -0.4]
    b.restore_state.assert_called_once_with(b'processor')
    b.restore_controller_state.assert_called_once_with(b'controller')
    assert [c[0] for c in b.method_calls].index('restore_state') < [c[0] for c in b.method_calls].index('restore_controller_state')
    assert supervisor.stats.controller_restorations == 1
    supervisor.close()


def test_unsupported_controller_is_safe_and_restores_component():
    a, b = _worker(), _worker()
    a.snapshot_controller_state.side_effect = NotImplementedError
    supervisor = SupervisedVST3Worker(Mock(side_effect=[a, b]))
    supervisor.process(BLOCK)
    assert supervisor.checkpoint_full_state() == (b'processor', None)
    supervisor.reset_session()
    supervisor.process(BLOCK)
    b.restore_state.assert_called_once_with(b'processor')
    b.restore_controller_state.assert_not_called()
    assert supervisor.stats.unsupported_controllers == 1
    supervisor.close()


def test_failed_controller_checkpoint_does_not_publish_partial_component_state():
    a, b = _worker(), _worker()
    supervisor = SupervisedVST3Worker(Mock(side_effect=[a, b]), max_restarts=1)
    supervisor.process(BLOCK)
    assert supervisor.checkpoint_full_state() == (b'processor', b'controller')
    a.snapshot_state.return_value = b'new processor'
    a.snapshot_controller_state.side_effect = RuntimeError('controller IPC down')
    with pytest.raises(RuntimeError):
        supervisor.checkpoint_full_state()
    a.close.assert_called_once_with(force=True)
    supervisor.process(BLOCK)
    b.restore_state.assert_called_once_with(b'processor')
    b.restore_controller_state.assert_called_once_with(b'controller')
    assert supervisor.stats.checkpoints == 1
    supervisor.close()


def test_controller_snapshot_error_and_optional_capability():
    w = _worker()
    supervisor = SupervisedVST3Worker(lambda: w)
    supervisor.process(BLOCK)
    assert supervisor.checkpoint_controller_state() == b'controller'
    assert supervisor.stats.controller_checkpoints == 1
    w.snapshot_controller_state.side_effect = NotImplementedError
    assert supervisor.checkpoint_controller_state() is None
    assert supervisor.stats.unsupported_controllers == 1
    supervisor.clear_checkpoint()
    supervisor.close()


def test_controller_snapshot_invalid_rejected():
    w = _worker()
    w.snapshot_controller_state.return_value = b'x' * (1024 * 1024 + 1)
    supervisor = SupervisedVST3Worker(lambda: w)
    supervisor.process(BLOCK)
    with pytest.raises(Exception, match='exceeds snapshot budget'):
        supervisor.checkpoint_controller_state()
    w.close.assert_called_once_with(force=True)
    supervisor.close()
