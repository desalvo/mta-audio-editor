"""Real SQLite contention must not turn a transient policy read into cancellation."""
from contextlib import closing
import sqlite3
import threading
import time

import pytest

from app import auth, ai_metering_agent as agent, resource_accounts as resources
from app.sqlite_availability import BarrierUnavailable
from test_r210_subscriptions import account as account, plan  # noqa: F401


@pytest.mark.parametrize('limited', [False, True])
def test_worker_retries_a_fresh_original_policy_read_after_exclusive_writer(account, monkeypatch, limited):
    if limited:
        plan(account)
    assert resources.has_limits(account) is limited
    locked, release, finished = threading.Event(), threading.Event(), threading.Event()
    def write():
        with closing(sqlite3.connect(auth.db_path())) as con:
            con.execute('BEGIN EXCLUSIVE')
            locked.set()
            try:
                assert release.wait(5)
            finally:
                con.rollback()
                finished.set()
    thread = threading.Thread(target=write)
    thread.start()
    assert locked.wait(5)
    original = resources.has_limits
    attempts = []
    def read(uid):
        attempts.append(uid)
        try:
            return original(uid)
        except BarrierUnavailable as exc:
            assert exc.retryable
            release.set()
            assert finished.wait(5)
            raise
    monkeypatch.setattr(resources, 'has_limits', read)
    try:
        assert agent._worker_has_resource_limits(account) is limited
    finally:
        release.set()
        thread.join(5)
    assert not thread.is_alive() and attempts == [account, account]


def test_worker_policy_retry_exhaustion_keeps_the_original_unavailable_error(account, monkeypatch):
    original = resources.has_limits
    errors = []
    def read(uid):
        try:
            return original(uid)
        except BarrierUnavailable as exc:
            errors.append(exc)
            raise
    monkeypatch.setattr(resources, 'has_limits', read)
    with closing(sqlite3.connect(auth.db_path())) as writer:
        writer.execute('BEGIN EXCLUSIVE')
        began = time.monotonic()
        try:
            with pytest.raises(BarrierUnavailable) as raised:
                agent._worker_has_resource_limits(account)
        finally:
            writer.rollback()
    assert len(errors) == 4 and raised.value is errors[-1]
    assert raised.value.retryable and time.monotonic() - began < 3
    assert original(account) is False


@pytest.mark.parametrize('failure', [BarrierUnavailable(None),
    BarrierUnavailable(sqlite3.OperationalError('database disk image is malformed')),
    sqlite3.OperationalError('no such table: resource_memberships')])
def test_damaged_evidence_is_never_retried_or_treated_as_unlimited(monkeypatch, failure):
    calls = []
    def fail(uid):
        calls.append(uid)
        raise failure
    monkeypatch.setattr(resources, 'has_limits', fail)
    with pytest.raises(type(failure)) as raised:
        agent._worker_has_resource_limits(123)
    assert raised.value is failure and calls == [123]
