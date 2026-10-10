"""R51-R60: bounded offline multi-request VST3 session protocol tests."""
import math
import struct
from unittest.mock import patch

import pytest

from native.vst3_probe.offline_session import (
    MAGIC, _pack_requests, _unpack_requests, render_native_session,
)
from native.vst3_probe.native_chain import NativeChainError


def test_packed_envelope_multiple_jobs():
    payload = _pack_requests([[0.25, -0.25], [0.5]], 1, 44100)
    assert payload[:8] == MAGIC
    assert struct.unpack_from('<III', payload, 8) == (1, 44100, 2)
    assert _unpack_requests(payload, [2, 1], 1, 44100) == [[0.25, -0.25], [0.5]]


def test_stereo_preserves_interleaved_order():
    value = [[0.125, -0.125, 0.5, -0.5], [0.0, 1.0]]
    assert _unpack_requests(_pack_requests(value, 2, 96000), [2, 1], 2, 96000) == value


@pytest.mark.parametrize('requests,channels,rate', [
    ([], 1, 48000), ([[1.0]], 3, 48000), ([[1.0]], 1, 32000),
    ([[0.1]], True, 48000), ([[math.nan]], 1, 48000),
    ([[math.inf]], 1, 48000), ([[17.0]], 1, 48000),
    ([[True]], 1, 48000), ([[0.1]], 2, 48000),
    ([[0.0]] * 129, 1, 48000),
])
def test_reject_invalid_envelopes(requests, channels, rate):
    with pytest.raises(ValueError):
        _pack_requests(requests, channels, rate)


def test_reject_cumulative_frame_overflow():
    with pytest.raises(ValueError, match='cumulative'):
        _pack_requests([[0.0] * 1048576, [0.0]], 1, 48000)


@pytest.mark.parametrize('corrupt', [
    lambda p: p[:8] + b'BAD!' + p[12:],
    lambda p: p[:20] + struct.pack('<I', 3) + p[24:],
    lambda p: p[:-1],
    lambda p: p + b'x',
    lambda p: p[:16] + struct.pack('<I', 3) + p[20:],
])
def test_reject_corrupt_response(corrupt):
    with pytest.raises(NativeChainError):
        _unpack_requests(corrupt(_pack_requests([[0.0]], 1, 48000)), [1], 1, 48000)


def test_validate_before_invoking_executable():
    with patch('subprocess.run') as run:
        with pytest.raises(ValueError, match='CID'):
            render_native_session([[0.2]], ('missing.vst3', 'bad'), '/missing/probe')
        run.assert_not_called()


def test_native_probe_session_contract():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / 'native/vst3_probe/main.cpp').read_text()
    assert '"--render-session"' in source
    assert 'MTASPCM1' in source
    assert 'sessionFrames.push_back(frames)' in source
    assert 'processor->setupProcessing(setup)' in source
    assert 'native_host_ready' in source


def test_session_chain_preserves_job_order_and_isolation():
    from native.vst3_probe.offline_session import render_native_session_chain
    calls = []
    def fake(requests, plugin, executable, **kwargs):
        calls.append(plugin)
        return [[sample + 0.25 for sample in request] for request in requests]
    with patch('native.vst3_probe.offline_session.render_native_session', side_effect=fake):
        result = render_native_session_chain([[0.0], [1.0]], [('a', '1' * 32), ('b', '2' * 32)], '/probe')
    assert result == [[0.5], [1.5]]
    assert len(calls) == 2


def test_session_chain_rejects_empty_inserts():
    from native.vst3_probe.offline_session import render_native_session_chain
    with pytest.raises(ValueError, match='inserts'):
        render_native_session_chain([[0.0]], [], '/probe')
