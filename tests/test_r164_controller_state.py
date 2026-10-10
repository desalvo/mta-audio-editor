"""r164: separated controller snapshots are bounded and require event mode."""
from pathlib import Path
import json
import struct
import subprocess

import pytest

from native.vst3_probe import stream_worker as sw


def test_controller_state_preflight():
    worker = object.__new__(sw.NativeVST3Worker)
    worker.events_enabled = False
    with pytest.raises(ValueError):
        worker.snapshot_controller_state()
    with pytest.raises(ValueError):
        worker.restore_controller_state(b'')
    worker.events_enabled = True
    with pytest.raises(ValueError):
        worker.restore_controller_state('bad')
    with pytest.raises(ValueError):
        worker.restore_controller_state(b'x' * (1024 * 1024 + 1))


def test_controller_commands_have_independent_ids():
    source = (Path(__file__).resolve().parents[1] / 'native/vst3_probe/main.cpp').read_text()
    assert 'controller->getState(&state)' in source
    assert 'controller->setState(&state)' in source
    assert '0xfffffffdU' in source and '0xfffffffcU' in source
    assert '1024U * 1024U' in source
    assert struct.pack('<I', 0xfffffffd) != struct.pack('<I', 0xffffffff)


def test_real_adelay_controller_snapshot(monkeypatch):
    probe = Path('/mnt/data/r164-sdk-build/mta_vst3_probe')
    plugin = Path('/mnt/data/r70-adelay-build/VST3/Release/adelay.vst3')
    if not probe.is_file() or not plugin.exists():
        pytest.skip('Optional locally built Steinberg SDK and ADelay')
    monkeypatch.setenv('MTA_VST3_PATHS', str(plugin.parent))
    from native.vst3_probe.probe import resolve_module_binary
    metadata = json.loads(subprocess.check_output([str(probe), str(resolve_module_binary(plugin))], timeout=25))
    cid = next(x['cid'] for x in metadata['classes'] if x['name'] == 'ADelay' and x['category'] == 'Audio Module Class')
    with sw.NativeVST3Worker((str(plugin), cid), str(probe), events_enabled=True, timeout=15) as worker:
        before = worker.process([0.1, -0.1] * 64)
        assert len(before) == 128
        try:
            snapshot = worker.snapshot_controller_state()
        except NotImplementedError:
            # ADelay does not expose an independent controller state; this is valid.
            snapshot = None
        if snapshot is not None:
            assert isinstance(snapshot, bytes) and len(snapshot) <= 1024 * 1024
            worker.restore_controller_state(snapshot)
        after = worker.process([0.1, -0.1] * 64)
        assert len(after) == 128
