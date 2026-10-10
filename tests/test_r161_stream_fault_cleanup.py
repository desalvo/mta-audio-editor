"""r161: a failed single-block IPC transfer never leaves a reusable worker."""
from types import SimpleNamespace
import pytest
from native.vst3_probe.stream_worker import NativeVST3Worker
from native.vst3_probe.native_chain import NativeChainError


class FakeProcess:
    def __init__(self):
        self.killed = 0
        self.returncode = None
        self.stdin = SimpleNamespace(close=lambda: None)
        self.stdout = SimpleNamespace(close=lambda: None)

    def poll(self):
        return self.returncode

    def kill(self):
        self.killed += 1
        self.returncode = -9

    def wait(self, timeout=None):
        return self.returncode


@pytest.mark.parametrize('error', [NativeChainError('truncated'), OSError('pipe failure')])
def test_single_block_ipc_error_terminates_worker(error):
    worker = object.__new__(NativeVST3Worker)
    import threading
    worker._lock = threading.Lock()
    worker._closed = False
    worker._proc = FakeProcess()
    worker.channels = 2
    worker.events_enabled = False
    worker.timeout = 0.1

    def fail(*_):
        raise error

    worker._exchange = fail
    with pytest.raises(type(error)):
        worker.process([0.25, -0.25] * 16)
    assert worker._closed
    assert worker._proc.killed == 1
    with pytest.raises(NativeChainError, match='closed'):
        worker.process([0.25, -0.25] * 16)
