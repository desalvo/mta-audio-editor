"""r166: portable checkpoint persistence and atomic state recovery."""
import json
from unittest.mock import Mock

import pytest

from native.vst3_probe.native_chain import NativeChainError
from native.vst3_probe.state_store import (decode_checkpoint, encode_checkpoint,
                                           load_checkpoint, save_checkpoint)
from native.vst3_probe.stream_worker import EventBlock
from native.vst3_probe.supervised_worker import SupervisedVST3Worker

PLUGIN = "plugin.vst3#0123456789abcdef0123456789abcdef"


def _worker():
    w = Mock(channels=2, events_enabled=True)
    w.process_event_batch.return_value = [[0.25, -0.25]]
    w.snapshot_state.return_value = b"processor"
    w.snapshot_controller_state.return_value = b"controller"
    return w


def test_roundtrip_and_controller_optional(tmp_path):
    path = tmp_path / "checkpoint.json"
    save_checkpoint(path, PLUGIN, b"component", b"controller")
    assert load_checkpoint(path, PLUGIN) == (b"component", b"controller")
    assert load_checkpoint(path, PLUGIN) == decode_checkpoint(path.read_bytes(), PLUGIN)
    save_checkpoint(path, PLUGIN, b"", None)
    assert load_checkpoint(path, PLUGIN) == (b"", None)
    assert not list(tmp_path.glob("*.tmp"))


def test_bad_plugin_tamper_and_truncation(tmp_path):
    blob = encode_checkpoint(PLUGIN, b"a", b"b")
    with pytest.raises(NativeChainError):
        decode_checkpoint(blob, "wrong.plugin")
    with pytest.raises(NativeChainError):
        decode_checkpoint(blob[:-1], PLUGIN)
    payload = json.loads(blob)
    payload["payload"]["component"] = "ZGFtYWdlZA=="
    with pytest.raises(NativeChainError):
        decode_checkpoint(json.dumps(payload).encode(), PLUGIN)
    with pytest.raises(NativeChainError):
        decode_checkpoint(b"x" * (3 * 1024 * 1024 + 1), PLUGIN)
    path = tmp_path / "bad.json"
    path.write_bytes(blob + b"!" * (3 * 1024 * 1024))
    with pytest.raises(NativeChainError):
        load_checkpoint(path, PLUGIN)


def test_limits_are_enforced():
    with pytest.raises(ValueError):
        encode_checkpoint(PLUGIN, b"x" * (1024 * 1024 + 1), None)
    with pytest.raises(ValueError):
        encode_checkpoint("", b"a", None)
    with pytest.raises(ValueError):
        encode_checkpoint(PLUGIN, b"a", b"x" * (1024 * 1024 + 1))


def test_supervisor_rehydrates_saved_pair_after_restart(tmp_path):
    original = _worker()
    first = SupervisedVST3Worker(lambda: original)
    first.process(EventBlock([0.1, -0.1]))
    first.checkpoint_full_state()
    path = tmp_path / "plugin.state"
    first.export_checkpoint(path, PLUGIN)
    first.close()
    new = _worker()
    next_session = SupervisedVST3Worker(lambda: new)
    next_session.import_checkpoint(path, PLUGIN)
    assert next_session.process(EventBlock([0.1, -0.1])) == [0.25, -0.25]
    new.restore_state.assert_called_once_with(b"processor")
    new.restore_controller_state.assert_called_once_with(b"controller")
    next_session.close()


def test_bad_import_preserves_previous_checkpoint(tmp_path):
    worker = _worker()
    s = SupervisedVST3Worker(lambda: worker)
    save_checkpoint(tmp_path / "ok", PLUGIN, b"good", None)
    s.import_checkpoint(tmp_path / "ok", PLUGIN)
    (tmp_path / "bad").write_bytes(b"broken")
    with pytest.raises(NativeChainError):
        s.import_checkpoint(tmp_path / "bad", PLUGIN)
    s.process(EventBlock([0.1, -0.1]))
    worker.restore_state.assert_called_once_with(b"good")
    with pytest.raises(RuntimeError):
        s.import_checkpoint(tmp_path / "ok", PLUGIN)
    s.close()
