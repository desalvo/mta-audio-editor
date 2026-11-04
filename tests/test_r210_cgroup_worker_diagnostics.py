from io import BytesIO

from app.ai_cgroup_metering import _BoundedStderr, _ERROR_TAIL_LIMIT, _safe_worker_error


def test_worker_stderr_is_drained_and_bounded():
    reader = _BoundedStderr(BytesIO(b'prefix' * 5000 + b'\nRuntimeError: worker exited\n'))
    result = reader.finish()
    assert result.endswith('RuntimeError: worker exited\n')
    assert len(result.encode()) <= _ERROR_TAIL_LIMIT


def test_worker_diagnostic_redacts_secret_and_url():
    raw = ('some user input\n'
           'RuntimeError: password=secret-value token=abc123 https://private.example/a\n')
    diagnostic = _safe_worker_error(raw)
    assert 'RuntimeError' in diagnostic
    assert 'secret-value' not in diagnostic
    assert 'abc123' not in diagnostic
    assert 'private.example' not in diagnostic
    assert 'some user input' not in diagnostic


def test_worker_diagnostic_does_not_echo_unstructured_stderr():
    assert _safe_worker_error('user supplied prompt line') == 'no safe exception detail in stderr'


def test_chord_download_exit_exposes_fixed_diagnostic_only(monkeypatch):
    import subprocess

    import pytest

    from app.ai_models import _isolated_model_download

    def failed(argv, **kwargs):
        assert argv[1] == '-I'
        return subprocess.CompletedProcess(argv, 1, '', 'urllib.error.HTTPError: HTTP Error 404: private URL')

    monkeypatch.setattr(subprocess, 'run', failed)
    with pytest.raises(RuntimeError, match='model_download_http_404') as exc:
        _isolated_model_download('/installed/python', 'chords-ml', 'chordformer')
    assert 'private URL' not in str(exc.value)
