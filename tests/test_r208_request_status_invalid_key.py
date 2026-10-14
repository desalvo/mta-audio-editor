import pytest
from app import ai_request_dedup

@pytest.mark.parametrize('bad_key', [None, True, False, 12, {}, [], b'not-text', '', 'bad', 'x' * 129])
def test_request_status_rejects_noncanonical_keys_without_touching_database(monkeypatch, bad_key):
    monkeypatch.setattr(ai_request_dedup, 'db', lambda: pytest.fail('Invalid key must not query database'))
    with pytest.raises(ValueError, match='Invalid AI idempotency key'):
        ai_request_dedup.request_status(1, bad_key)
