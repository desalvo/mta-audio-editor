"""The VST3 batch preflight must never invoke a plugin or modify files."""
import json
import wave
from pathlib import Path
from unittest.mock import patch

import pytest

from native.vst3_probe.batch_wav_cli import run_batch, main

CID = 'a' * 32


def manifest(tmp_path: Path, *, rate=48000, frames=41):
    with wave.open(str(tmp_path / 'source.wav'), 'wb') as wav:
        wav.setnchannels(2)
        wav.setsampwidth(3)
        wav.setframerate(rate)
        wav.writeframes(b'\0' * (frames * 2 * 3))
    data = {'schema': 1, 'jobs': [{'source': 'source.wav', 'destination': 'out.wav',
                                    'plugins': [['fake.vst3', CID]]}]}
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(data))
    return path


def test_preflight_validates_wav_without_running_plugins(tmp_path):
    m = manifest(tmp_path)
    with patch('native.vst3_probe.batch_wav_cli.render_native_wav', side_effect=AssertionError('must not execute')):
        result = run_batch(m, '/missing/probe', dry_run=True)
    assert result['status'] == 'ready'
    assert result['processed'] == 0
    assert result['results'][0]['frames'] == 41
    assert result['results'][0]['channels'] == 2
    assert result['results'][0]['bit_depth'] == 24
    assert not (tmp_path / 'out.wav').exists()


def test_preflight_rejects_incompatible_rate(tmp_path):
    m = manifest(tmp_path, rate=44100)
    with pytest.raises(ValueError, match='Unsupported WAV'):
        run_batch(m, '/missing/probe', dry_run=True)


def test_preflight_rejects_missing_output_directory(tmp_path):
    m = manifest(tmp_path)
    body = json.loads(m.read_text())
    body['jobs'][0]['destination'] = 'missing/out.wav'
    m.write_text(json.dumps(body))
    with pytest.raises(ValueError, match='Output folder'):
        run_batch(m, '/missing/probe', dry_run=True)


def test_cli_dry_run(tmp_path, capsys):
    m = manifest(tmp_path)
    rc = main([str(m), '--probe', '/nonexistent', '--dry-run'])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)['status'] == 'ready'


def test_normal_mode_unchanged(tmp_path):
    m = manifest(tmp_path)
    with patch('native.vst3_probe.batch_wav_cli.render_native_wav', return_value=tmp_path/'source.wav') as mock:
        result = run_batch(m, '/probe')
    assert result['status'] == 'ok'
    assert mock.call_count == 1
