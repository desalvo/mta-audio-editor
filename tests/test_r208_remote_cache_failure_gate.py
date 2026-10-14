"""Both remote ingress routes must fail closed when durable result storage fails."""
from pathlib import Path
import ast


def test_both_ingress_routes_require_durable_result_before_completion():
    import app.ai_billing_routes as routes
    tree = ast.parse(Path(routes.__file__).read_text())
    functions = {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    for name in ('execute_remote_ai_job', 'execute_remote_ai_audio_job'):
        source = ast.get_source_segment(Path(routes.__file__).read_text(), functions[name])
        cache_start = source.index('save_result(identity[')
        completion = source.index("dedup.finalize(identity['user_id'], key, job_id=worker_job_id)")
        failure = source.index("dedup.finalize(identity['user_id'], key, state='failed')", cache_start)
        assert cache_start < failure < completion
        assert 'Remote AI result could not be durably published' in source
        assert 'except (OSError, ValueError) as exc:' in source


def test_dedup_failed_request_never_readmitted(monkeypatch, tmp_path):
    from app import ai_request_dedup as dedup
    import sqlite3
    from contextlib import contextmanager
    file = tmp_path / 'admission.db'
    @contextmanager
    def local_db():
        con = sqlite3.connect(file)
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        finally:
            con.close()
    monkeypatch.setattr(dedup, 'db', local_db)
    key = 'durable-cache-error-12345'
    digest = dedup.fingerprint('whisper', b'{}', b'abc')
    dedup.admit(10, key, digest)
    dedup.finalize(10, key, state='failed')
    assert dedup.request_status(10, key)['state'] == 'failed'
    import pytest
    with pytest.raises(dedup.DuplicateAIRequest) as exc:
        dedup.admit(10, key, digest)
    assert exc.value.state == 'failed'
