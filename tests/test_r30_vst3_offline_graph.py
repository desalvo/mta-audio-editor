import pytest

from native.vst3_probe.offline_graph import (
    PluginTiming, compensate_latency, align_parallel_stems,
    mix_aligned, pending_tail_frames,
)


def test_compensated_impulse():
    assert compensate_latency([[0, 0, 1, 2, 3]], 2, target_frames=3) == [[1, 2, 3]]


def test_short_flushed_output_pads():
    assert compensate_latency([[0, 1]], 1, target_frames=4) == [[1, 0, 0, 0]]


def test_parallel_latency_alignment():
    stems = [[[1.0, 2.0, 3.0]], [[0.0, 0.0, 2.0]]]
    aligned = align_parallel_stems(stems, [PluginTiming(0, 0), PluginTiming(2, 0)])
    assert aligned == [[[0.0, 0.0, 1.0, 2.0, 3.0]], [[0.0, 0.0, 2.0, 0.0, 0.0]]]
    assert mix_aligned(aligned) == [[0.0, 0.0, 3.0, 2.0, 3.0]]


def test_tail_budget():
    assert pending_tail_frames([PluginTiming(0, 300), PluginTiming(5, 200)]) == 500


@pytest.mark.parametrize('latency', [-1, 480001, 1.5, True])
def test_invalid_latency(latency):
    with pytest.raises(ValueError):
        PluginTiming(latency, 0)


def test_nonfinite_rejected():
    with pytest.raises(ValueError):
        compensate_latency([[float('nan')]], 0)


def test_mismatched_channels_rejected():
    with pytest.raises(ValueError):
        mix_aligned([[[1.0]], [[1.0], [2.0]]])


def test_realtime_still_gated():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "native/vst3_probe/probe.py").read_text()
    assert "'native_host_ready': False" in source


def test_event_boundary_and_ordering():
    from native.vst3_probe.offline_graph import ScheduledEvent, events_for_blocks
    events = [ScheduledEvent(512, 'note_off'), ScheduledEvent(0, 'note_on'),
              ScheduledEvent(512, 'parameter', parameter_id=3, value=0.5)]
    batches = events_for_blocks(events, block_size=512, frames=1024)
    assert [off for off, _ in batches[0]] == [0]
    assert [off for off, _ in batches[1]] == [0, 0]
    assert [event.kind for _, event in batches[1]] == ['note_off', 'parameter']


def test_partial_final_block_and_invalid_event():
    from native.vst3_probe.offline_graph import ScheduledEvent, events_for_blocks
    assert events_for_blocks([ScheduledEvent(1024, 'note_on')], block_size=512, frames=1025)[-1][0][0] == 0
    with pytest.raises(ValueError):
        events_for_blocks([ScheduledEvent(1025, 'note_on')], block_size=512, frames=1025)
    with pytest.raises(ValueError):
        ScheduledEvent(0, 'parameter', value=float('nan'))
