from app.ai_job_queue import AIJobQueue


def test_ai_jobs_planning_cancel_security_and_capacity():
    q = AIJobQueue()
    job = q.submit('proj1', 'alice', 'remix', {'prompt': 'swing'})
    assert job['status'] == 'planned' and not job['generation_available']
    assert q.get(job['id'], 'proj1', 'bob') is None
    assert q.cancel(job['id'], 'proj1', 'bob') is None
    assert q.cancel(job['id'], 'proj1', 'alice')['status'] == 'cancelled'
    assert q.get(job['id'], 'proj1', 'alice')['status'] == 'cancelled'
    for _ in range(128):
        q.submit('p', 'a', 'rearrange', {'style': 'jazz'})
    assert q.get(job['id'], 'proj1', 'alice') is None
