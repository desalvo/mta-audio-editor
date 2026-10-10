"""State-continuous WAV export and atomic failure behavior."""
import wave
from pathlib import Path
from unittest.mock import patch
import pytest
from native.vst3_probe.offline_session import render_native_session_wav


def make_wav(path: Path, *, frames=29, channels=2, width=3, rate=44100):
    with wave.open(str(path), 'wb') as writer:
        writer.setnchannels(channels)
        writer.setsampwidth(width)
        writer.setframerate(rate)
        writer.writeframes(b'\x00' * frames * channels * width)


@pytest.mark.parametrize('width', [2, 3, 4])
@pytest.mark.parametrize('channels', [1, 2])
def test_session_wav_preserves_format_and_segments(tmp_path, width, channels):
    source, dest = tmp_path / 'in.wav', tmp_path / 'out.wav'
    make_wav(source, width=width, channels=channels)
    def identity(requests, plugins, executable, **kwargs):
        assert [len(x) // channels for x in requests] == [11, 11, 7]
        assert kwargs['sample_rate'] == 44100
        return requests
    with patch('native.vst3_probe.offline_session.render_native_session_chain', side_effect=identity):
        assert render_native_session_wav(source, dest, [('plugin', '0' * 32)], 'probe', block_frames=11) == dest
    with wave.open(str(dest), 'rb') as reader:
        assert (reader.getnframes(), reader.getnchannels(), reader.getsampwidth(), reader.getframerate()) == (29, channels, width, 44100)


def test_failure_does_not_replace_destination(tmp_path):
    source, dest = tmp_path / 'in.wav', tmp_path / 'out.wav'
    make_wav(source)
    dest.write_bytes(b'preserve')
    with patch('native.vst3_probe.offline_session.render_native_session_chain', side_effect=RuntimeError('plugin failed')):
        with pytest.raises(RuntimeError, match='plugin failed'):
            render_native_session_wav(source, dest, [('plugin', '0' * 32)], 'probe')
    assert dest.read_bytes() == b'preserve'


def test_hardlinks_are_protected(tmp_path):
    import os
    source, dest = tmp_path / 'in.wav', tmp_path / 'out.wav'
    make_wav(source)
    os.link(source, dest)
    with pytest.raises(ValueError, match='distinct'):
        render_native_session_wav(source, dest, [('plugin', '0' * 32)], 'probe')


def test_invalid_blocks_and_oversized_counts(tmp_path):
    source, dest = tmp_path / 'in.wav', tmp_path / 'out.wav'
    make_wav(source, frames=129)
    for block in (0, -1, 1.1, True):
        with pytest.raises(ValueError):
            render_native_session_wav(source, dest, [('plugin', '0' * 32)], 'probe', block_frames=block)
    with pytest.raises(ValueError, match='too many blocks'):
        render_native_session_wav(source, dest, [('plugin', '0' * 32)], 'probe', block_frames=1)
