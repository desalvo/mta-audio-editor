"""Batch WAV manifest guards and deterministic isolated export behavior."""
import json
import struct
import wave
from unittest.mock import patch

import pytest

from native.vst3_probe.batch_wav_cli import main, run_batch


def _manifest(tmp_path, jobs):
    path = tmp_path / 'batch.json'
    path.write_text(json.dumps({'schema': 1, 'jobs': jobs}))
    return path


def _wav(path):
    with wave.open(str(path), 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(48000)
        wav.writeframes(struct.pack('<hhh', 12, -24, 36))


def _job(source='a.wav', destination='out.wav'):
    return {'source': source, 'destination': destination, 'plugins': [['example.vst3', 'a' * 32]]}


def test_batch_two_exports(tmp_path, capsys):
    _wav(tmp_path / 'a.wav')
    _wav(tmp_path / 'b.wav')
    manifest = _manifest(tmp_path, [_job(), _job('b.wav', 'out2.wav')])
    with patch('native.vst3_probe.native_chain.render_native_chain', side_effect=lambda audio, *a, **kw: audio):
        assert main([str(manifest), '--probe', 'not-needed']) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == 'ok' and result['processed'] == 2
    assert (tmp_path / 'out.wav').exists() and (tmp_path / 'out2.wav').exists()


@pytest.mark.parametrize('jobs', [[], [_job(), _job('a.wav', 'out.wav')], [_job('a.wav', 'a.wav')],
                                  [_job('a.wav', 'b.wav'), _job('b.wav', 'out.wav')]])
def test_manifest_preflight_rejects_invalid_jobs(tmp_path, jobs):
    _wav(tmp_path / 'a.wav')
    _wav(tmp_path / 'b.wav')
    with pytest.raises(ValueError):
        run_batch(_manifest(tmp_path, jobs), 'probe')


def test_existing_output_preserved_on_error(tmp_path):
    _wav(tmp_path / 'a.wav')
    target = tmp_path / 'out.wav'
    target.write_bytes(b'original')
    manifest = _manifest(tmp_path, [_job()])
    with patch('native.vst3_probe.batch_wav_cli.render_native_wav', side_effect=RuntimeError('unexpected')):
        with pytest.raises(RuntimeError):
            run_batch(manifest, 'probe')
    assert target.read_bytes() == b'original'


def test_stop_on_error_and_continue(tmp_path):
    _wav(tmp_path / 'a.wav')
    _wav(tmp_path / 'b.wav')
    manifest = _manifest(tmp_path, [_job(), _job('b.wav', 'out2.wav')])
    from native.vst3_probe.native_chain import NativeChainError
    with patch('native.vst3_probe.batch_wav_cli.render_native_wav', side_effect=NativeChainError('failed')):
        assert run_batch(manifest, 'probe', stop_on_error=True)['processed'] == 1
        assert run_batch(manifest, 'probe', stop_on_error=False)['processed'] == 2


def test_invalid_timeout_rejected(tmp_path):
    _wav(tmp_path / 'a.wav')
    with pytest.raises(ValueError):
        run_batch(_manifest(tmp_path, [_job()]), 'probe', timeout=float('nan'))
