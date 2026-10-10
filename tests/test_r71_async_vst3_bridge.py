"""r71 asynchronous VST3 bridge regression tests."""
import time

import pytest

from native.vst3_probe.async_bridge import AsyncVST3Bridge


class FakeWorker:
    def __init__(self, *, broken=False):
        self.broken = broken
        self.calls = []
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return None
    def process(self, samples):
        self.calls.append(samples)
        if self.broken:
            raise RuntimeError('plugin crashed')
        return [value * 0.5 for value in samples]


def wait_result(bridge):
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        response = bridge.poll()
        if response is not None:
            return response
        time.sleep(0.005)
    pytest.fail('Timed out waiting for bridge result')


def test_order_and_stereo_result():
    factory = FakeWorker()
    with AsyncVST3Bridge(lambda: factory, channels=2) as bridge:
        for index in range(3):
            assert bridge.submit([float(index), 2.0]) == index
            result = wait_result(bridge)
            assert result.sequence == index
            assert result.samples == (index * 0.5, 1.0)
            assert result.error is None
    assert len(factory.calls) == 3


def test_error_is_latched_and_terminates_worker():
    with AsyncVST3Bridge(lambda: FakeWorker(broken=True), channels=1) as bridge:
        assert bridge.submit([0.1]) == 0
        result = wait_result(bridge)
        assert 'plugin crashed' in result.error
        assert bridge.submit([0.2]) is None
        assert bridge.fault is not None


@pytest.mark.parametrize('values', [[], [float('nan')], [float('inf')], [17.0], [True]])
def test_bad_samples_rejected(values):
    with AsyncVST3Bridge(FakeWorker, channels=1) as bridge:
        with pytest.raises(ValueError):
            bridge.submit(values)


def test_factory_crash_and_shutdown():
    def broken_factory():
        raise RuntimeError('load failed')
    bridge = AsyncVST3Bridge(broken_factory)
    assert bridge.close()
    assert bridge.fault is not None
    assert bridge.submit([0.0, 0.0]) is None


def test_bounded_backpressure_and_overflow():
    import threading
    gate = threading.Event()
    class BlockedWorker(FakeWorker):
        def process(self, samples):
            gate.wait(1)
            return super().process(samples)
    bridge = AsyncVST3Bridge(BlockedWorker, capacity=1, channels=1)
    try:
        # Depending on scheduling, the first request might have been consumed.
        accepted = [bridge.submit([0.0]) for _ in range(20)]
        assert any(item is None for item in accepted)
    finally:
        gate.set()
        assert bridge.close()


def test_reject_large_and_invalid_config():
    with pytest.raises(ValueError):
        AsyncVST3Bridge(FakeWorker, capacity=0)
    with AsyncVST3Bridge(FakeWorker, channels=2) as bridge:
        with pytest.raises(ValueError):
            bridge.submit([1.0])
        with pytest.raises(ValueError):
            bridge.submit([0.0] * 1026)
