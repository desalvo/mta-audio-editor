"""Offline native render rates must be validated and propagated end to end."""
import wave
from pathlib import Path
from unittest.mock import patch
import pytest
from native.vst3_probe.native_chain import render_native_chain, render_native_wav
from native.vst3_probe.batch_wav_cli import run_batch

@pytest.mark.parametrize('rate', [44100, 48000, 96000])
def test_reject_bool_and_invalid_rates(rate):
    with pytest.raises(ValueError, match='Sample rate'):
        render_native_chain([0.0], [('plugin', 'a'*32)], '/probe', sample_rate=True)
    with pytest.raises(ValueError, match='Sample rate'):
        render_native_chain([0.0], [('plugin', 'a'*32)], '/probe', sample_rate=12345)

def test_cpp_transport_uses_requested_rate():
    code = (Path(__file__).resolve().parents[1] / 'native/vst3_probe/main.cpp').read_text()
    assert 'pcmSampleRate = std::stoi(rate)' in code
    assert 'setup.sampleRate = static_cast<double>(pcmSampleRate)' in code
    assert 'transport.sampleRate = static_cast<double>(pcmSampleRate)' in code

def test_wav_preserves_44100_and_96000(tmp_path):
    for rate in (44100, 96000):
        source = tmp_path / f'{rate}.wav'
        target = tmp_path / f'{rate}-out.wav'
        with wave.open(str(source), 'wb') as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(rate)
            wav.writeframes(b'\0\0' * 65)
        with patch('native.vst3_probe.native_chain.render_native_chain', side_effect=lambda audio, *args, **kwargs: audio) as render:
            result = render_native_wav(source, target, [('plugin','a'*32)], '/probe')
        assert result == target
        assert render.call_args.kwargs['sample_rate'] == rate
        with wave.open(str(target), 'rb') as wav:
            assert (wav.getframerate(), wav.getnframes()) == (rate, 65)
