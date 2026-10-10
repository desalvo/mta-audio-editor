"""PCM24/PCM32 high-resolution WAV integration and safety regressions."""
import math
import wave
from unittest.mock import patch
import pytest
from native.vst3_probe.native_chain import NativeWavError, render_native_wav, _encode_pcm_wav, _decode_pcm_wav


@pytest.mark.parametrize('width', [2, 3, 4])
@pytest.mark.parametrize('channels', [1, 2])
def test_lossless_integer_pcm_roundtrip_with_isolated_identity(tmp_path, width, channels):
    src, dst = tmp_path/'input.wav', tmp_path/'output.wav'
    values = [0, 1, -1, 1 << (width * 8 - 3), -(1 << (width * 8 - 3))]
    raw = b''.join(int(v).to_bytes(width, 'little', signed=True) for v in values * channels)
    with wave.open(str(src), 'wb') as wf:
        wf.setnchannels(channels);wf.setsampwidth(width);wf.setframerate(48000);wf.writeframes(raw)
    with patch('native.vst3_probe.native_chain.render_native_chain', side_effect=lambda a, *args, **kw: a):
        render_native_wav(src, dst, [('plugin', 'f'*32)], 'probe')
    with wave.open(str(dst), 'rb') as wf:
        assert (wf.getsampwidth(), wf.getnchannels(), wf.getnframes()) == (width, channels, len(values))
        output = wf.readframes(len(values))
    assert output == raw


def test_pcm24_sign_extension_and_clipping():
    decoded = _decode_pcm_wav(b'\x00\x00\x80\xff\xff\x7f', 3)
    assert decoded[0] == -1.0 and decoded[1] > 0.99999
    assert _encode_pcm_wav([-2., 2.], 3) == b'\x00\x00\x80\xff\xff\x7f'


def test_nan_and_wrong_frame_count_do_not_publish(tmp_path):
    src, dst = tmp_path/'in.wav', tmp_path/'out.wav'
    with wave.open(str(src), 'wb') as wf:
        wf.setnchannels(1);wf.setsampwidth(3);wf.setframerate(48000);wf.writeframes(b'\x00\x00\x00' * 8)
    dst.write_bytes(b'original')
    for bad in [[math.nan]*8, [0.0]*7]:
        with patch('native.vst3_probe.native_chain.render_native_chain', return_value=bad):
            with pytest.raises(NativeWavError):
                render_native_wav(src, dst, [('plugin', 'f'*32)], 'probe')
        assert dst.read_bytes() == b'original'
