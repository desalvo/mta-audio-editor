"""Retry original queue observation after bounded BUSY,never worker execution."""
from contextlib import contextmanager
import sqlite3
import threading

import pytest
from app import ai_arranger_runtime as queue,ai_global_execution as execution
from app import regime_service_lease as leases
from app.sqlite_availability import BarrierUnavailable
from app.regime_operation_fence import FenceBlocked
from test_r210_queue_identity_stem_metering import env as env  # noqa: F401


@contextmanager
def exclusive_queue():
    con=sqlite3.connect(queue._ROOT/'jobs.sqlite3',isolation_level=None,timeout=2)
    try:
        con.execute('PRAGMA locking_mode=EXCLUSIVE')
        con.execute('BEGIN EXCLUSIVE')
        yield con
    finally:
        con.close()


def terminal_row(env):
    queue.start('fixture','worker:markers',None,job_id='original-busy-job',defer_spawn=True,
        payload={'schema_version':1,'actor_user_id':env,'kind':'markers'})
    with queue._db() as con:con.execute("UPDATE jobs SET state='completed' WHERE job_id='original-busy-job'")


def test_actual_exclusive_queue_read_recovers_original_state(env,monkeypatch):
    terminal_row(env)
    original=leases.fence_held;busy=[]
    with exclusive_queue() as lock:
        def inspect(connection=None):
            try:return original(connection)
            except BarrierUnavailable as exc:
                assert exc.retryable
                busy.append(exc);lock.rollback();lock.close()
                raise
        monkeypatch.setattr(leases,'fence_held',inspect)
        state=queue.get('original-busy-job')
    assert len(busy)==1 and state['job_id']=='original-busy-job' and state['state']=='completed'


def test_persistent_exclusive_queue_is_still_unavailable_after_three_attempts(env,monkeypatch):
    terminal_row(env);original=queue._db;attempts=[]
    def connect():attempts.append(True);return original()
    monkeypatch.setattr(queue,'_db',connect)
    with exclusive_queue(),pytest.raises(BarrierUnavailable) as error:
        queue.get('original-busy-job')
    assert error.value.retryable and len(attempts)==3
    assert queue.get('original-busy-job')['state']=='completed'


@pytest.mark.parametrize('error',[
    BarrierUnavailable(None),BarrierUnavailable(sqlite3.OperationalError('database disk image is malformed')),
    FenceBlocked('Service maintenance remains active'),sqlite3.OperationalError('no such table: jobs')])
def test_unknown_barrier_maintenance_and_other_sql_errors_are_not_retried(env,monkeypatch,error):
    attempts=[]
    def connect():attempts.append(True);raise error
    monkeypatch.setattr(queue,'_db',connect)
    with pytest.raises(type(error)) as observed:queue.get('original-busy-job')
    assert observed.value is error and len(attempts)==1


def test_missing_job_is_not_retried_or_recreated(env,monkeypatch):
    terminal_row(env);original=queue._db;attempts=[]
    def connect():attempts.append(True);return original()
    monkeypatch.setattr(queue,'_db',connect)
    assert queue.get('absent-job') is None and len(attempts)==1
    assert len(queue.list_jobs())==1


@pytest.mark.parametrize('worker_failure',[False,True])
def test_actual_execution_preserves_result_error_and_identity_after_busy_terminal_poll(env,monkeypatch,worker_failure):
    from app.ai_metering_agent import WorkerUncertain
    original_get=queue.get;original_fence=leases.fence_held;calls=[];busy=[];jobs=[]
    main=threading.current_thread();failure=WorkerUncertain('Original worker evidence retained',job_id='original-ledger')
    def observed(job_id):
        state=original_get(job_id)
        if threading.current_thread() is main and state['state'] in {'completed','failed'} and not jobs:
            jobs.append(job_id)
            with exclusive_queue() as lock:
                def inspect(connection=None):
                    try:return original_fence(connection)
                    except BarrierUnavailable as exc:
                        assert exc.retryable
                        busy.append(exc);lock.rollback();lock.close()
                        raise
                with monkeypatch.context() as context:
                    context.setattr(leases,'fence_held',inspect)
                    return original_get(job_id)
        return state
    monkeypatch.setattr(queue,'get',observed)
    def worker(cancelled):
        calls.append(True)
        if worker_failure:raise failure
        return b'original-result'
    if worker_failure:
        with pytest.raises(WorkerUncertain) as error:execution.execute(env,'markers',worker)
        assert error.value is failure and error.value.job_id=='original-ledger'
    else:assert execution.execute(env,'markers',worker)==b'original-result'
    assert calls==[True] and len(jobs)==1 and len(busy)==1
    rows=queue.list_jobs();assert len(rows)==1 and rows[0]['job_id']==jobs[0]
