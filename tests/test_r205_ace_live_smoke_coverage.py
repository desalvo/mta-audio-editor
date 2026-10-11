"""Exercise real smoke worker orchestration branches without model downloads."""
from pathlib import Path
import subprocess
import wave

import pytest
from app import ace_step_live_smoke as smoke


class Completed:
    def __init__(self, code=0):
        self.returncode = code


def _valid_wav(path: Path):
    with wave.open(str(path), 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(44100)
        wav.writeframes(b'\0\0' * 80)


@pytest.mark.parametrize('case,expected', [
    ('success', 'audio_generated'),
    ('exit', 'worker_smoke_failed'),
    ('missing', 'invalid_generated_audio'),
    ('corrupt', 'invalid_generated_audio'),
    ('timeout', 'timeout'),
])
def test_worker_smoke_result_branches(monkeypatch, tmp_path, case, expected):
    worker = tmp_path / 'worker.py'
    worker.write_text('# mock')
    monkeypatch.setattr(smoke, 'configured_worker', lambda: worker)

    def run(argv, **kwargs):
        assert '--smoke-input' in argv and '--output' in argv
        source = Path(argv[argv.index('--smoke-input') + 1])
        assert source.is_file()
        output = Path(argv[argv.index('--output') + 1])
        if case == 'timeout':
            raise subprocess.TimeoutExpired(argv, 5)
        if case == 'success':
            _valid_wav(output)
        if case == 'corrupt':
            output.write_bytes(b'invalid wav')
        return Completed(1 if case == 'exit' else 0)

    monkeypatch.setattr(smoke.subprocess if hasattr(smoke, 'subprocess') else subprocess, 'run', run)
    answer = smoke.test_live_inference(seconds=1, timeout_seconds=5)
    assert answer['attempted'] is True
    assert answer['verified'] == (case == 'success')
    assert answer['reason'] == expected
    if case == 'success':
        assert answer['audio']["frames"] > 0


def test_cli_success_and_failure(monkeypatch, capsys):
    monkeypatch.setattr(smoke, 'test_live_inference', lambda **kw: {'attempted': True, 'verified': True, 'reason': 'ok'})
    monkeypatch.setattr('sys.argv', ['smoke', '--seconds', '2', '--timeout', '9'])
    assert smoke.main() == 0
    assert '"verified": true' in capsys.readouterr().out

    def rejected(**kw):
        raise ValueError('invalid seconds')
    monkeypatch.setattr(smoke, 'test_live_inference', rejected)
    assert smoke.main() == 1
    assert 'invalid seconds' in capsys.readouterr().out
