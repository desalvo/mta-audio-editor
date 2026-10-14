"""Regression checks for asynchronous web Arranger submission and queue polling."""
import json
import time
from threading import Event
from app import ai_arranger_runtime as runtime


def test_queued_work_reports_position_without_starting_concurrently(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime, '_ROOT', tmp_path)
    entered, finish = Event(), Event()
    def work(progress):
        entered.set()
        assert finish.wait(5)
    _, a = runtime.start('p1', 'arranger', work)
    assert entered.wait(2)
    _, b = runtime.start('p2', 'arranger', lambda _: None)
    assert runtime.inspect('p2')['state'] == 'queued'
    assert runtime.inspect('p2')['queue_position'] == 1
    finish.set()
    for _ in range(120):
        if runtime.inspect('p2')['state'] == 'completed':
            break
        time.sleep(.02)
    assert runtime.inspect('p2')['state'] == 'completed'
    assert runtime.inspect('p1')['job_id'] == a['job_id']
    assert runtime.inspect('p2')['job_id'] == b['job_id']


def test_progress_only_from_worker(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime, '_ROOT', tmp_path)
    entered, finish = Event(), Event()
    def work(progress):
        progress.write_text(json.dumps({'phase': 'inference', 'progress_percent': 37, 'cpu_seconds': 2.5}))
        entered.set()
        finish.wait(5)
    _, job = runtime.start('p1', 'arranger', work)
    assert entered.wait(2)
    assert runtime.inspect('p1')['progress_percent'] == 37
    assert runtime.inspect('p1')['cpu_seconds'] == 2.5
    (tmp_path / (job['job_id'] + '.progress.json')).write_text(json.dumps({'phase': 'inference', 'progress_percent': 270}))
    assert runtime.inspect('p1')['progress_percent'] is None
    finish.set()


def test_frontend_polling_contract():
    from pathlib import Path
    js = (Path(__file__).resolve().parents[1] / 'app/static/app.js').read_text()
    assert '/ai-arranger/active-generation' in js
    assert 'start-generation' in js
    assert "job.state==='queued'" in js
    assert 'aiArrangerWatchTimer=setInterval(poll,2000)' in js
