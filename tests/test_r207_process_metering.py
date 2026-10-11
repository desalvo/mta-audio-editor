import os
import sys
import pytest
from app.ai_metering_agent import run_metered_process

@pytest.mark.skipif(os.name != 'posix' or not hasattr(os, 'wait4'), reason='Linux process accounting')
def test_metered_child_cpu_and_io(tmp_path):
    result = run_metered_process([sys.executable, '-c', 'sum(i*i for i in range(250000)); open("out", "wb").write(b"z" * 4096)'], cwd=str(tmp_path), timeout_seconds=10)
    assert result.exit_code == 0
    assert result.usage['cpu_seconds'] >= 0
    assert 'gpu_seconds' not in result.usage
    assert (tmp_path / 'out').stat().st_size == 4096

@pytest.mark.skipif(os.name != 'posix' or not hasattr(os, 'wait4'), reason='Linux process accounting')
def test_metering_timeout(tmp_path):
    result = run_metered_process([sys.executable, '-c', 'import time; time.sleep(4)'], cwd=str(tmp_path), timeout_seconds=1)
    assert result.exit_code != 0
    assert result.elapsed_seconds < 3

def test_invalid_invocation(tmp_path):
    with pytest.raises(ValueError):
        run_metered_process([], cwd=str(tmp_path))


def test_registered_worker_error_is_tracked(tmp_path, monkeypatch):
    from app.auth import db, init_auth_db
    from app import ai_metering_agent
    monkeypatch.setenv('MTA_DATA_DIR',str(tmp_path/'db'))
    init_auth_db()
    with db() as con:
        con.execute("INSERT INTO users(username,email,password_hash,active,role,created_at,updated_at) VALUES('meter','meter@example.org','x',1,'user',1,1)")
        uid=con.execute("SELECT id FROM users WHERE username='meter'").fetchone()[0]
    worker=tmp_path/'worker.py'
    worker.write_text('import sys\nsys.exit(4)\n')
    monkeypatch.setattr('app.ai_worker_protocol.configured_worker',lambda:worker)
    with pytest.raises(Exception,match='failed'):
        ai_metering_agent.execute_registered_worker(uid,'ace-step',{'model_id':'test'})
    with db() as con:
        row=con.execute("SELECT status,resource_source FROM ai_compute_jobs").fetchone()
        assert row['status']=='failed' and row['resource_source']=='worker'

@pytest.mark.skipif(os.name != 'posix' or not hasattr(os, 'wait4'), reason='Linux process accounting')
def test_no_host_cpu_is_charged(tmp_path):
    import threading
    stop = threading.Event()
    def burn():
        while not stop.is_set():
            sum(i * i for i in range(1000))
    thread = threading.Thread(target=burn)
    thread.start()
    try:
        measure = run_metered_process([sys.executable, '-c', 'import time; time.sleep(0.35)'],
                                      cwd=str(tmp_path), timeout_seconds=5)
    finally:
        stop.set()
        thread.join()
    assert measure.isolated
    assert 0 <= measure.usage['cpu_seconds'] < 4  # per-child wait4, not host aggregate
    assert 'gpu_seconds' not in measure.usage
    assert 'gpu_energy_joules' not in measure.usage


def test_no_double_counting_of_output_payload():
    from pathlib import Path
    source = Path(__file__).resolve().parents[1] / 'app' / 'ai_metering_agent.py'
    text = source.read_text()
    assert "usage.get('disk_write_bytes', 0) + len(payload)" not in text
