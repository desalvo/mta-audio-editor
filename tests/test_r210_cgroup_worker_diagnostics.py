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
