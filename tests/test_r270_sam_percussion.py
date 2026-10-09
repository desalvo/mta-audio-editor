from pathlib import Path
from unittest.mock import patch
import pytest
from app import main


def test_sam_rejects_unknown_model_or_instrument(tmp_path):
    with pytest.raises(ValueError):
        main._sam_audio_extract(tmp_path / 'in.wav', tmp_path, 'invalid', 'kick')
    with pytest.raises(ValueError):
        main._sam_audio_extract(tmp_path / 'in.wav', tmp_path, 'sam-audio-small', 'invalid')


def test_sam_requires_separate_configured_runtime(tmp_path, monkeypatch):
    monkeypatch.delenv('MTA_SAM_AUDIO_PYTHON', raising=False)
    with pytest.raises(RuntimeError, match='MTA_SAM_AUDIO_PYTHON'):
        main._sam_audio_extract(tmp_path / 'in.wav', tmp_path, 'sam-audio-small', 'percussions')


def test_sam_worker_invokes_requested_instrument(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_SAM_AUDIO_PYTHON', '/optional/python')
    def fake_run(args, **kwargs):
        assert args[0] == '/optional/python'
        assert args[args.index('--prompt') + 1] == main._SAM_PROMPTS['cymbals']
        Path(args[args.index('--output') + 1]).write_bytes(b'RIFF' + b'0'*60)
        return type('Process', (), {'returncode': 0, 'stderr': '', 'stdout': ''})()
    with patch.object(main.subprocess if hasattr(main, 'subprocess') else __import__('subprocess'), 'run', side_effect=fake_run):
        output = main._sam_audio_extract(tmp_path / 'drums.wav', tmp_path / 'output', 'sam-audio-base', 'cymbals')
    assert output.is_file()


def test_sam_configuration_is_available_in_both_workflows():
    js = Path('app/static/app.js').read_text()
    assert 'trackPercussionMethod' in js and 'stemPercussionMethod' in js
    assert 'rememberPercussionMethod' in js
    assert 'percussion_method' in js
    for key in ('kick', 'snare', 'toms', 'cymbals'):
        assert f'value="{key}"' in js
