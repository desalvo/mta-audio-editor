"""Latency accounting and reference dry path alignment for experimental IPC."""
import pytest
from native.vst3_probe.latency_plan import LatencyPlan, PCMDelayLine


def test_latency_sample_rate_and_lookahead():
    plan = LatencyPlan(48000, 256, 384, 3)
    assert plan.ipc_latency_frames == 768
    assert plan.total_latency_frames == 1152
    assert plan.total_latency_ms == 24


def test_compensation_never_advances_audio():
    fast = LatencyPlan(48000, 256, 0, 2)
    slow = LatencyPlan(48000, 256, 128, 3)
    assert fast.compensation_frames(slow) == 384
    assert slow.compensation_frames(fast) == 0


def test_reference_delay_mono_across_irregular_blocks():
    line = PCMDelayLine(3, channels=1)
    assert line.process((1.0, 2.0)) == (0.0, 0.0)
    assert line.process((3.0, 4.0, 5.0)) == (0.0, 1.0, 2.0)
    assert line.process((6.0,)) == (3.0,)
    line.reset()
    assert line.process((7.0,)) == (0.0,)


def test_reference_delay_stereo_is_channel_independent():
    line = PCMDelayLine(1, channels=2)
    assert line.process((1.0, 10.0, 2.0, 20.0)) == (0.0, 0.0, 1.0, 10.0)
    assert line.process((3.0, 30.0)) == (2.0, 20.0)


def test_zero_delay_identity():
    line = PCMDelayLine(0, channels=2)
    assert line.process((.5, -.5)) == (.5, -.5)


@pytest.mark.parametrize('args', [(-1,), (960001,), (True,)])
def test_invalid_delay(args):
    with pytest.raises(ValueError):
        PCMDelayLine(*args)


@pytest.mark.parametrize('rate,block,plugin,lookahead', [(32000, 128, 0, 1), (48000, 513, 0, 1),
    (48000, 256, -1, 1), (48000, 256, 0, 0), (48000, 256, 0, 257)])
def test_invalid_latency_plan(rate, block, plugin, lookahead):
    with pytest.raises(ValueError):
        LatencyPlan(rate, block, plugin, lookahead)
