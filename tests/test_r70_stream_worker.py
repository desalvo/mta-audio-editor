"""Interactive VST3 IPC offline worker framing, validation, and atomic export."""
from pathlib import Path
import struct
import wave

import pytest
from native.vst3_probe import stream_worker as sw
from native.vst3_probe.native_chain import NativeChainError


def test_protocol_roundtrip_and_malformed_frame_rejection():
    data = sw._encode_block([0.25, -0.125, 0.5, -0.5], 2)
    assert struct.unpack_from('<I', data)[0] == 2
    assert sw._decode_block(data, 2, 2) == pytest.approx([0.25, -0.125, 0.5, -0.5])
    with pytest.raises(NativeChainError):
        sw._decode_block(data, 1, 2)
    with pytest.raises(NativeChainError):
        sw._decode_block(struct.pack('<I', 2) + b'\xff\xff\xff\x7f'*4, 2, 2)
    with pytest.raises(ValueError):
        sw._encode_block([0.0] * 513, 1)
    with pytest.raises(ValueError):
        sw._encode_block([float('nan')], 1)
    with pytest.raises(ValueError):
        sw._encode_block([True], 1)
    with pytest.raises(ValueError):
        sw._encode_block([17.0], 1)


class DummyWorker:
    started = []
    fail_after = None

    def __init__(self, plugin, executable, *, channels, sample_rate, timeout):
        self.calls = 0
        self.started.append((channels, sample_rate))

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def process(self, pcm):
        self.calls += 1
        if self.fail_after is not None and self.calls > self.fail_after:
            raise NativeChainError('injected plugin failure')
        return list(pcm)


def test_streaming_wav_is_chunk_bounded_and_preserves_format(tmp_path, monkeypatch):
    monkeypatch.setattr(sw, 'NativeVST3Worker', DummyWorker)
    source, dest = tmp_path/'in.wav', tmp_path/'out.wav'
    pcm = b'\x00\x08' * 2 * 2001
    with wave.open(str(source), 'wb') as f:
        f.setnchannels(2); f.setsampwidth(2); f.setframerate(44100); f.writeframes(pcm)
    DummyWorker.fail_after = None
    sw.render_stream_wav(source, dest, [('plugin', 'cid')], 'probe')
    assert DummyWorker.started[-1] == (2, 44100)
    with wave.open(str(dest), 'rb') as f:
        assert (f.getnframes(), f.getframerate(), f.getnchannels()) == (2001, 44100, 2)
        assert f.readframes(2001) == pcm
    with pytest.raises(ValueError):
        sw.render_stream_wav(source, source, [('plugin', 'cid')], 'probe')
    with pytest.raises(sw.NativeWavError):
        sw.render_stream_wav(source, dest, [('plugin', 'cid')], 'probe', max_total_frames=2000)


def test_streaming_wav_failure_keeps_existing_output(tmp_path, monkeypatch):
    monkeypatch.setattr(sw, 'NativeVST3Worker', DummyWorker)
    source, dest = tmp_path/'in.wav', tmp_path/'existing.wav'
    with wave.open(str(source), 'wb') as f:
        f.setnchannels(1); f.setsampwidth(3); f.setframerate(96000)
        f.writeframes(b'\0'*3*1200)
    dest.write_bytes(b'protected-original')
    DummyWorker.fail_after = 1
    with pytest.raises(NativeChainError):
        sw.render_stream_wav(source, dest, [('plugin', 'cid')], 'probe')
    assert dest.read_bytes() == b'protected-original'
    assert not list(tmp_path.glob('.mta-vst3-stream-*'))
    DummyWorker.fail_after = None


def test_acceptance_workflow_is_required():
    root = Path(__file__).resolve().parents[1]
    ci = (root/'.github/workflows/ci-cd.yml').read_text()
    assert 'python scripts/test_vst3_adelay_stream.py' in ci
    assert '--stream-pcm' in (root/'native/vst3_probe/main.cpp').read_text()
    assert 'native_host_ready' in (root/'native/vst3_probe/main.cpp').read_text()
