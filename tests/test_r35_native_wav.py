"""WAV conversion/atomic publish regression tests (no SDK runtime required)."""
import struct
import wave
from unittest.mock import patch
import pytest
from native.vst3_probe.native_chain import NativeWavError, render_native_wav


def wav_file(path, *, channels=2, rate=48000, width=2, frames=777):
    with wave.open(str(path), 'wb') as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(width)
        wav.setframerate(rate)
        wav.writeframes(struct.pack('<' + 'h' * (frames * channels), *([2048] * (frames * channels))) if width == 2 else bytes(frames * channels * width))


def test_stereo_roundtrip_wav(tmp_path):
    source = tmp_path / 'in.wav'
    output = tmp_path / 'out.wav'
    wav_file(source)
    with patch('native.vst3_probe.native_chain.render_native_chain', side_effect=lambda a, *args, **kw: a) as renderer:
        assert render_native_wav(source, output, [('p','f'*32)], 'probe') == output
    assert renderer.call_count == 1
    with wave.open(str(output), 'rb') as wav:
        assert (wav.getnchannels(), wav.getnframes(), wav.getframerate()) == (2, 777, 48000)
        assert wav.readframes(777) == source.read_bytes()[44:]


def test_mono_and_partial_frames(tmp_path):
    source = tmp_path / 'in.wav'
    output = tmp_path / 'out.wav'
    wav_file(source, channels=1, frames=513)
    with patch('native.vst3_probe.native_chain.render_native_chain', side_effect=lambda a, *args, **kw: a):
        render_native_wav(source, output, [('p','f'*32)], 'probe')
    with wave.open(str(output), 'rb') as wav:
        assert wav.getnframes() == 513


@pytest.mark.parametrize('settings', [{'rate':44100}, {'channels':3}, {'width':1}])
def test_reject_unsupported_wav(tmp_path, settings):
    source = tmp_path / 'in.wav'
    wav_file(source, **settings)
    with pytest.raises(NativeWavError):
        render_native_wav(source, tmp_path / 'out.wav', [('p','f'*32)], 'probe')


def test_failed_plugin_does_not_overwrite_output(tmp_path):
    source = tmp_path / 'in.wav'
    output = tmp_path / 'out.wav'
    wav_file(source)
    output.write_bytes(b'existing export')
    with patch('native.vst3_probe.native_chain.render_native_chain', side_effect=RuntimeError('plugin failed')):
        with pytest.raises(RuntimeError, match='plugin failed'):
            render_native_wav(source, output, [('p','f'*32)], 'probe')
    assert output.read_bytes() == b'existing export'
    assert not list(tmp_path.glob('.mta-vst3-*'))


def test_reject_overwriting_source(tmp_path):
    source = tmp_path / 'in.wav'
    wav_file(source)
    with pytest.raises(ValueError, match='differ'):
        render_native_wav(source, source, [('p','f'*32)], 'probe')
