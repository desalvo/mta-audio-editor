"""r61-r65: continuous sample clock and defensive bounded session input."""
from pathlib import Path
import pytest
from native.vst3_probe.offline_session import _pack_requests, _unpack_requests

ROOT = Path(__file__).resolve().parents[1]

def test_valid_irregular_mono_requests():
    jobs = [[0.125] * 17, [0.25] * 777, [-0.5] * 3]
    assert _unpack_requests(_pack_requests(jobs, 1, 44100), [17, 777, 3], 1, 44100) == jobs

def test_valid_irregular_stereo_requests():
    jobs = [[0.5, -0.5] * 3, [0.125, -0.125] * 529]
    assert _unpack_requests(_pack_requests(jobs, 2, 96000), [3, 529], 2, 96000) == jobs

@pytest.mark.parametrize('value', [b'bad', 'bad', [b'bad'], ['bad'], [iter([1.0])]])
def test_invalid_request_container(value):
    with pytest.raises((ValueError, TypeError)):
        _pack_requests(value, 1, 48000)

def test_oversized_request_fails_before_copying():
    with pytest.raises(ValueError, match='cumulative'):
        _pack_requests([[0.0] * (1048576 + 1)], 1, 48000)

def test_native_transport_uses_processed_frames():
    source = (ROOT / 'native/vst3_probe/main.cpp').read_text()
    assert 'processedSampleFrames += validFrames' in source
    assert 'const auto projectSample = processedSampleFrames' in source
    assert 'previousValidFrames = validFrames' in source
    assert 'projectSample != offlineLastProjectSample + previousValidFrames' in source
    assert 'native_host_ready' in source
