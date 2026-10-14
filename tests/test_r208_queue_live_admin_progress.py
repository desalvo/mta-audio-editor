"""Live worker measurements must agree for job owners and administrators."""
import json
from threading import Event
import time
from app import ai_arranger_runtime as queue


def test_live_progress_is_visible_to_admin_and_owner(tmp_path, monkeypatch):
    monkeypatch.setattr(queue, '_ROOT', tmp_path)
    queue.configure(1)
    entered, release = Event(), Event()
    def work(progress):
        progress.write_text(json.dumps({'phase': 'diffusion', 'progress_percent': 23.5,
                                        'cpu_seconds': 4.25, 'gpu_seconds': 1.5}))
        entered.set()
        assert release.wait(5)
    job = queue.start('project-1', 'ace-step', work)[1]
    try:
        assert entered.wait(5)
        owner = queue.get(job['job_id'])
        admin = next(j for j in queue.list_jobs() if j['job_id'] == job['job_id'])
        inspected = queue.inspect('project-1')
        for data in (owner, admin, inspected):
            assert data['phase'] == 'diffusion'
            assert data['progress_percent'] == 23.5
            assert data['cpu_seconds'] == 4.25
            assert data['gpu_seconds'] == 1.5
        (tmp_path / (job['job_id'] + '.progress.json')).write_text(json.dumps({
            'progress_percent': 150, 'cpu_seconds': -1, 'gpu_seconds': 'guess',
        }))
        invalid = queue.get(job['job_id'])
        assert invalid['progress_percent'] is None
        assert invalid['cpu_seconds'] is None
        assert invalid['gpu_seconds'] is None
    finally:
        release.set()
    for _ in range(100):
        if queue.get(job['job_id'])['state'] == 'completed':
            break
        time.sleep(0.05)
    assert queue.get(job['job_id'])['state'] == 'completed'
