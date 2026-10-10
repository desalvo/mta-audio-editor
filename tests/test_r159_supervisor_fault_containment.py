"""r159: fail closed on unexpected plugin/adapter errors and malformed replies."""
from unittest.mock import Mock

import pytest

from native.vst3_probe.stream_worker import EventBlock
from native.vst3_probe.supervised_worker import SupervisedVST3Worker


def worker(reply=None, error=None):
    value = Mock(channels=2, events_enabled=True)
    if error is not None:
        value.process_event_batch.side_effect = error
    else:
        value.process_event_batch.return_value = reply
    return value


@pytest.mark.parametrize('bad_reply', [None, [], [[], []], [None], [[0.2]], [[float('inf'), 1]], 'invalid'])
def test_malformed_worker_reply_always_falls_back_and_discards(bad_reply):
    bad = worker(bad_reply)
    good = worker([[0.7, 0.6]])
    factory = Mock(side_effect=[bad, good])
    supervisor = SupervisedVST3Worker(factory, max_restarts=1)
    dry = EventBlock([0.1, -0.1])
    assert supervisor.process(dry) == [0.1, -0.1]
    bad.close.assert_called_once_with(force=True)
    assert supervisor.stats.faults == 1
    assert supervisor.process(dry) == [0.7, 0.6]
    assert supervisor.stats.epoch == 2
    supervisor.close()


def test_unexpected_processor_exception_is_contained():
    bad = worker(error=RuntimeError('unexpected adapter failure'))
    next_worker = worker([[0.4, 0.5]])
    supervisor = SupervisedVST3Worker(Mock(side_effect=[bad, next_worker]), max_restarts=1)
    block = EventBlock([0.15, 0.25])
    assert supervisor.process(block) == [0.15, 0.25]
    bad.close.assert_called_once_with(force=True)
    assert supervisor.process(block) == [0.4, 0.5]
    bad.process_event_batch.assert_called_once()
    supervisor.close()


def test_base_exceptions_are_not_masked():
    bad = worker(error=KeyboardInterrupt())
    supervisor = SupervisedVST3Worker(lambda: bad)
    with pytest.raises(KeyboardInterrupt):
        supervisor.process(EventBlock([0.1, 0.2]))
    supervisor.close()
