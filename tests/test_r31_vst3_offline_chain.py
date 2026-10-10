"""End-to-end deterministic offline render graph acceptance tests."""
from collections import deque
import math
import pytest
from native.vst3_probe.offline_graph import (
    PluginTiming, OfflineInsert, OfflineRenderError, ScheduledEvent, render_insert_chain,
)


def gain(value):
    return lambda block, events: [[sample * value for sample in channel] for channel in block]


def delay(n):
    q = None
    def process(block, events):
        nonlocal q
        if q is None:
            q = [deque([0.] * n) for _ in block]
        out = []
        for channel, buf in zip(block, q):
            samples = []
            for value in channel:
                buf.append(value)
                samples.append(buf.popleft())
            out.append(samples)
        return out
    return process


def test_chain_gain_and_latency_compensation():
    result = render_insert_chain([[1., 2., 3., 4.]], [
        OfflineInsert('delay', PluginTiming(3, 0), delay(3)),
        OfflineInsert('gain', PluginTiming(0, 0), gain(2.)),
    ], block_size=2)
    assert result.audio == [[2., 4., 6., 8.]]
    assert result.latency_samples == 3
    assert result.blocks_processed == 8


def test_stereo_and_partial_final_block():
    r = render_insert_chain([[1., 2., 3.], [4., 5., 6.]], [
        OfflineInsert('gain', PluginTiming(0, 0), gain(.25))], block_size=2)
    assert r.audio == [[.25, .5, .75], [1., 1.25, 1.5]]
    assert r.blocks_processed == 2


def test_events_sample_offset_boundary_preserved():
    seen = []
    def track(block, events):
        seen.append([(offset, event.kind) for offset, event in events])
        return block
    events = [ScheduledEvent(4, 'note_off'), ScheduledEvent(0, 'note_on'),
              ScheduledEvent(5, 'parameter', parameter_id=4, value=.5)]
    r = render_insert_chain([[1.] * 7], [OfflineInsert('events', PluginTiming(0, 0), track)],
                            events=events, block_size=4)
    assert seen == [[(0, 'note_on')], [(0, 'note_off'), (1, 'parameter')]]
    assert r.events_dispatched == 3


def test_tail_flush_and_output_length():
    def echo():
        prev = 0.
        def process(block, events):
            nonlocal prev
            out = []
            for value in block[0]:
                out.append(value + prev * .5)
                prev = value
            return [out]
        return process
    r = render_insert_chain([[1., 0.]], [OfflineInsert('echo', PluginTiming(0, 2), echo())],
                            block_size=2, include_tail=True)
    assert r.audio == [[1., .5, 0., 0.]]
    assert r.tail_samples == 2


@pytest.mark.parametrize('bad', ['nan', 'wrong_channels', 'wrong_frames', 'exception'])
def test_fail_closed_during_render(bad):
    def broken(block, events):
        if bad == 'nan': return [[math.nan] * len(block[0])]
        if bad == 'wrong_channels': return []
        if bad == 'wrong_frames': return [[0.]]
        raise RuntimeError('plugin crashed')
    with pytest.raises(OfflineRenderError, match='Insert 0'):
        render_insert_chain([[1., 2.]], [OfflineInsert('broken', PluginTiming(0, 0), broken)])


def test_limits_and_invalid_events():
    chain = [OfflineInsert('gain', PluginTiming(0, 0), gain(1.))]
    with pytest.raises(ValueError): render_insert_chain([[1.]], chain * 33)
    with pytest.raises(ValueError): render_insert_chain([[1.]], chain, block_size=0)
    with pytest.raises(ValueError): render_insert_chain([[1.]], chain, events=[ScheduledEvent(1, 'note_on')])
