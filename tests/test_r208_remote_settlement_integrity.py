"""Remote billable request must never advertise an invalid response as completed."""
import pytest
from fastapi import HTTPException
from app.ai_billing_routes import _verified_worker_response

@pytest.mark.parametrize('result, meta, status', [
    (b'', {'job_id': 'job-x'}, 502),
    ('not-bytes', {'job_id': 'job-x'}, 502),
    (b'x' * 5, {'job_id': 'job-x'}, 413),
    (b'x', {}, 502),
    (b'x', {'job_id': 'bad\njob'}, 502),
    (b'x', {'job_id': 'ok-job', 'media_type': 'text/html'}, 502),
])
def test_invalid_worker_result_is_rejected(result, meta, status):
    with pytest.raises(HTTPException) as exc:
        _verified_worker_response(result, meta, max_bytes=4)
    assert exc.value.status_code == status


def test_valid_worker_result():
    assert _verified_worker_response(b'RIFF', {'job_id': 'id-123', 'media_type': 'audio/wav'}) == ('id-123','audio/wav')


def test_routes_validate_before_acknowledging():
    from pathlib import Path
    import app.ai_billing_routes as routes
    body = Path(routes.__file__).read_text()
    assert body.count('worker_job_id, worker_media_type = _verified_worker_response(result, meta)') == 2
    assert body.count("dedup.finalize(identity['user_id'], key, job_id=worker_job_id)") == 2
    assert 'Audio body length differs from Content-Length' in body
