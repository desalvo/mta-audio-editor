"""Bounded VST3 native state commands (offline SDK, not the realtime callback)."""
import json
from pathlib import Path
import subprocess

import pytest

from native.vst3_probe import stream_worker as sw

ROOT = Path(__file__).resolve().parents[1]


def test_state_controls_are_opt_in_and_bounded():
    source = (ROOT / 'native/vst3_probe/main.cpp').read_text()
    assert 'component->getState(&state)' in source
    assert 'component->setState(&state)' in source
    assert 'controller->setComponentState(&forController)' in source
    assert 'kMaxStateBytes = 1024U * 1024U' in source


def test_state_input_preflight():
    worker = object.__new__(sw.NativeVST3Worker)
    worker.events_enabled = False
    with pytest.raises(ValueError):
        worker.snapshot_state()
    with pytest.raises(ValueError):
        worker.restore_state(b'')
    worker.events_enabled = True
    with pytest.raises(ValueError):
        worker.restore_state(b'x' * (1024 * 1024 + 1))
    with pytest.raises(ValueError):
        worker.restore_state('untrusted')


def test_real_adelay_state_roundtrip(monkeypatch):
    binary = Path('/mnt/data/r163-sdk-build/mta_vst3_probe')
    plugin = Path('/mnt/data/r70-adelay-build/VST3/Release/adelay.vst3')
    if not binary.is_file() or not plugin.exists():
        pytest.skip('Optional locally built SDK and ADelay')
    monkeypatch.setenv('MTA_VST3_PATHS', str(plugin.parent))
    from native.vst3_probe.probe import resolve_module_binary
    metadata = json.loads(subprocess.check_output([str(binary), str(resolve_module_binary(plugin))], timeout=25))
    cid = next(x['cid'] for x in metadata['classes'] if x['name'] == 'ADelay' and x['category'] == 'Audio Module Class')
    with sw.NativeVST3Worker((str(plugin), cid), str(binary), events_enabled=True, timeout=15) as worker:
        a = worker.process([0.1, -0.1] * 64)
        assert len(a) == 128
        state = worker.snapshot_state()
        assert isinstance(state, bytes)
        assert len(state) <= 1024 * 1024
        worker.process_with_events([0.1, -0.1] * 64, parameters=[sw.ParameterPoint(100, 0, 0.2)])
        worker.restore_state(state)
        b = worker.process([0.1, -0.1] * 64)
        assert len(b) == 128


def test_supervisor_checkpoint_restored_after_fault():
    from unittest.mock import Mock
    from native.vst3_probe.supervised_worker import SupervisedVST3Worker
    first = Mock(channels=2, events_enabled=True)
    first.process_event_batch.side_effect = [[[0.4, 0.5]], RuntimeError('plugin crashed')]
    first.snapshot_state.return_value = b'processor state'
    second = Mock(channels=2, events_enabled=True)
    second.process_event_batch.return_value = [[0.7, 0.8]]
    supervisor = SupervisedVST3Worker(Mock(side_effect=[first, second]), max_restarts=1)
    block = sw.EventBlock([0.1, 0.2])
    assert supervisor.process(block) == [0.4, 0.5]
    assert supervisor.checkpoint_state() == b'processor state'
    assert supervisor.process(block) == [0.1, 0.2]
    assert supervisor.process(block) == [0.7, 0.8]
    second.restore_state.assert_called_once_with(b'processor state')
    assert supervisor.stats.checkpoints == 1
    assert supervisor.stats.restored_sessions == 1
    supervisor.close()


def test_failed_checkpoint_keeps_last_valid_snapshot():
    from unittest.mock import Mock
    from native.vst3_probe.supervised_worker import SupervisedVST3Worker
    a = Mock(channels=2, events_enabled=True)
    a.process_event_batch.return_value = [[0.3, 0.4]]
    a.snapshot_state.side_effect = [b'good', b'x' * (1024 * 1024 + 1)]
    b = Mock(channels=2, events_enabled=True)
    b.process_event_batch.return_value = [[0.5, 0.6]]
    supervisor = SupervisedVST3Worker(Mock(side_effect=[a, b]), max_restarts=1)
    block = sw.EventBlock([0.1, 0.2])
    supervisor.process(block)
    assert supervisor.checkpoint_state() == b'good'
    with pytest.raises(sw.NativeChainError):
        supervisor.checkpoint_state()
    assert supervisor.process(block) == [0.5, 0.6]
    b.restore_state.assert_called_once_with(b'good')
    assert supervisor.stats.checkpoints == 1
    supervisor.clear_checkpoint()
    supervisor.close()
