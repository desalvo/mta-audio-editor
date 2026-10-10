"""r33 variable-frame mono/stereo offline PCM transport contract."""
import math
from pathlib import Path
import pytest
from native.vst3_probe.native_chain import MAX_FRAMES, render_native_chain


def test_variable_frame_input_validation(tmp_path):
    exe = tmp_path / 'probe'
    exe.write_bytes(b'fake')
    plugins = [('fake.vst3', 'a'*32)]
    for audio in ([], [0.0] * (MAX_FRAMES + 1)):
        with pytest.raises(ValueError, match='1048576'):
            render_native_chain(audio, plugins, str(exe))
    for audio in ([(0.1,)], [(0.1, 0.2), (0.4,)], [(math.nan, 0.1)]):
        with pytest.raises(ValueError):
            render_native_chain(audio, plugins, str(exe))
    with pytest.raises(ValueError, match='PCM'):
        render_native_chain([math.inf], plugins, str(exe))


def test_native_variable_length_protocol_and_plugin_state():
    source = (Path(__file__).parents[1] / 'native/vst3_probe/main.cpp').read_text()
    assert 'kMaxPcmFrames = 1048576' in source
    assert 'pcmChannels' in source
    assert 'validFrames' in source
    assert 'data.numSamples = validFrames' in source
    assert 'std::min(channelIndex, pcmChannels - 1)' in source
    assert 'processor->process(data)' in source
    assert 'renderPcm ? static_cast<int>((pcmFrames + 511) / 512)' in source
