"""r32 fixed-length VST3 PCM subprocess chain security and acceptance contracts."""
import math
from pathlib import Path
import pytest
from native.vst3_probe.native_chain import FRAMES, NativeChainError, render_native_chain


def test_chain_rejects_invalid_buffers_before_any_plugin_load(tmp_path):
    exe = tmp_path / 'probe'
    exe.write_bytes(b'fake')
    with pytest.raises(ValueError, match='65536'):
        render_native_chain([0.0], [('x.vst3', 'f'*32)], str(exe))
    with pytest.raises(ValueError, match='PCM'):
        render_native_chain([0.0]*(FRAMES-1)+[math.nan], [('x.vst3', 'f'*32)], str(exe))
    with pytest.raises(ValueError, match='1..8'):
        render_native_chain([0.0]*FRAMES, [], str(exe))
    with pytest.raises(ValueError, match='CID'):
        render_native_chain([0.0]*FRAMES, [('bad.vst3', 'xyz')], str(exe))


def test_sdk_pcm_transport_exists_and_fail_closed():
    src = (Path(__file__).parents[1]/'native/vst3_probe/main.cpp').read_text()
    for marker in ('--render-pcm', 'kPcmFrames * sizeof(float)', 'pcmInput', 'pcmOutput',
                   'offlineProcessSucceeded', 'offlineNonFiniteSamples'):
        assert marker in src


def test_adapter_is_out_of_process_and_no_playback_activation():
    src = (Path(__file__).parents[1]/'native/vst3_probe/native_chain.py').read_text()
    assert 'subprocess.run(' in src
    assert 'TemporaryDirectory(' in src
    assert 'timeout=' in src
    assert 'native_host_ready' not in src
    assert 'pedalboard' not in src
