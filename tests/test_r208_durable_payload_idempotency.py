"""Regression checks for durable requests and replay safety."""
import pytest
from app import ai_arranger_runtime as q


def test_payload_is_durable_and_never_public(tmp_path, monkeypatch):
    monkeypatch.setattr(q, '_ROOT', tmp_path)
    q.configure(1)
    accepted, job = q.start('project', 'whisper', lambda path: None,
                            job_id='unique-payload', payload={'model': 'tiny', 'language': 'it'},
                            idempotency_key='request-unique')
    assert accepted
    assert q.read_payload(job['job_id']) == {'model': 'tiny', 'language': 'it'}
    assert 'payload_json' not in q.get(job['job_id'])
    assert 'idempotency_key' not in q.get(job['job_id'])
    assert 'payload_json' not in q.list_jobs()[0]
    accepted_again, again = q.start('project', 'whisper', lambda path: (_ for _ in ()).throw(AssertionError('duplicated')),
                                    job_id='different-id', payload={'model': 'tiny', 'language': 'it'},
                                    idempotency_key='request-unique')
    assert not accepted_again
    assert again['job_id'] == job['job_id']
    with pytest.raises(ValueError, match='Conflicting replay'):
        q.start('project', 'whisper', lambda path: None, payload={'model': 'different'}, idempotency_key='request-unique')


def test_reject_non_serializable_or_excessive_payload(tmp_path, monkeypatch):
    monkeypatch.setattr(q, '_ROOT', tmp_path)
    with pytest.raises(TypeError):
        q.start('p', 'whisper', lambda path: None, payload={'bad': object()})
    with pytest.raises(ValueError, match='exceeds'):
        q.start('p', 'whisper', lambda path: None, payload={'large': 'x' * (1024 * 1024)})
