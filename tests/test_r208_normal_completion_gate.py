"""Normal scheduler completion must honor durable publication/billing receipts."""
import time
import pytest
from app import ai_arranger_runtime as queue, ai_finalization

@pytest.mark.parametrize('receipt,expected', [
    ({'publication':'published','billing':None,'ready':True}, 'completed'),
    ({'publication':'pending','billing':None,'ready':False}, 'interrupted'),
    ({'publication':'published','billing':'delivered','ready':True}, 'completed'),
])
def test_normal_completion_gate(tmp_path, monkeypatch, receipt, expected):
    monkeypatch.setattr(queue, '_ROOT', tmp_path)
    monkeypatch.setattr(ai_finalization, 'readiness', lambda _jid: receipt)
    jid = 'r208normal' + str(len(receipt)) + ('yes' if expected == 'completed' else 'no')
    accepted, row = queue.start('p', 'arranger', lambda progress: None, job_id=jid, payload={'schema_version': 1, 'adapter': 'arranger'})
    assert accepted
    for _ in range(150):
        state = queue.get(jid)['state']
        if state not in ('queued', 'running'):
            break
        time.sleep(0.02)
    assert queue.get(jid)['state'] == expected


def test_non_audio_operation_keeps_original_completion(tmp_path, monkeypatch):
    monkeypatch.setattr(queue, '_ROOT', tmp_path)
    monkeypatch.setattr(ai_finalization, 'readiness', lambda _: pytest.fail('unexpected audio gate'))
    accepted, row = queue.start('p', 'other', lambda progress: None, job_id='r208notaudio')
    assert accepted
    for _ in range(150):
        if queue.get('r208notaudio')['state'] == 'completed':
            break
        time.sleep(0.02)
    assert queue.get('r208notaudio')['state'] == 'completed'
