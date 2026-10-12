"""Agentless GPU slot accounting never masquerades as measured GPU metering."""
import sqlite3

import pytest

from app import ai_gpu_slot_accounting as slots


@pytest.fixture
def slot_db(tmp_path, monkeypatch):
    path = tmp_path / 'slots.sqlite3'
    def connect():
        from contextlib import contextmanager
        @contextmanager
        def scoped():
            con = sqlite3.connect(path)
            con.row_factory = sqlite3.Row
            try:
                yield con
                con.commit()
            except BaseException:
                con.rollback()
                raise
            finally:
                con.close()
        return scoped()
    monkeypatch.setattr(slots, 'db', connect)
    with connect() as c:
        c.execute('CREATE TABLE ai_compute_jobs(id TEXT PRIMARY KEY, user_id INTEGER, status TEXT, billable INTEGER)')
        c.executemany('INSERT INTO ai_compute_jobs VALUES (?,?,?,?)',
                      [('a',1,'running',1),('b',2,'running',1),('c',3,'running',0)])
    return connect


def _finish(connect, *ids):
    with connect() as c:
        for key in ids:
            c.execute("UPDATE ai_compute_jobs SET status='done' WHERE id=?",(key,))


def test_two_concurrent_leases_share_one_capacity(slot_db):
    slots.acquire('a',at_ms=1000)
    slots.acquire('b',at_ms=1000)
    slots.release('a',at_ms=11000)
    slots.release('b',at_ms=11000)
    _finish(slot_db,'a','b')
    result = slots.preview(start_ms=1000,end_ms=11000,rate_micro_per_second=100)
    assert result['total_slot_seconds'] == 10
    assert [x['slot_seconds'] for x in result['jobs']] == [5,5]
    assert result['total_micro_eur'] == 1000
    assert result['not_an_invoice'] and result['external_gpu_activity_unobserved']


def test_unequal_overlap_and_waiting_not_charged(slot_db):
    slots.acquire('a',at_ms=1000)
    slots.acquire('b',at_ms=6000)
    slots.release('a',at_ms=11000)
    slots.release('b',at_ms=11000)
    _finish(slot_db,'a','b')
    rows = slots.preview(start_ms=1000,end_ms=11000)['jobs']
    assert [x['slot_seconds'] for x in rows] == [7.5,2.5]


def test_abort_not_charged(slot_db):
    slots.acquire('a',at_ms=1000)
    slots.release('a',at_ms=5000,aborted=True)
    _finish(slot_db,'a')
    row = slots.preview(start_ms=1000,end_ms=6000,rate_micro_per_second=1000)['jobs'][0]
    assert row['slot_seconds'] == 4
    assert row['micro_eur'] == 0


def test_diagnostic_job_not_charged(slot_db):
    slots.acquire('c',at_ms=1000)
    slots.release('c',at_ms=2000)
    _finish(slot_db,'c')
    assert slots.preview(start_ms=1000,end_ms=2000,rate_micro_per_second=100)['total_micro_eur'] == 0


def test_active_blocks_quotes_and_duplicate_leases(slot_db):
    slots.acquire('a',at_ms=1000)
    with pytest.raises(ValueError):
        slots.acquire('a',at_ms=1001)
    with pytest.raises(ValueError):
        slots.preview(start_ms=1000,end_ms=2000)
    slots.release('a',at_ms=2000)
    with pytest.raises(ValueError):
        slots.release('a',at_ms=2001)
    with pytest.raises(ValueError):
        slots.preview(start_ms=1000,end_ms=2000)


@pytest.mark.parametrize('gpu_key', ['../gpu','/invalid/gpu','', 'a b'])
def test_bad_device_id(slot_db,gpu_key):
    with pytest.raises(ValueError):
        slots.acquire('a',gpu_key,at_ms=1000)


def test_failed_job_no_charge(slot_db):
    slots.acquire('a',at_ms=1000)
    slots.release('a',at_ms=3000)
    with slot_db() as c:
        c.execute("UPDATE ai_compute_jobs SET status='failed' WHERE id='a'")
    assert slots.preview(start_ms=1000,end_ms=3000,rate_micro_per_second=1000)['total_micro_eur']==0


def test_rejects_bad_rates_and_timestamps(slot_db):
    with pytest.raises(ValueError):
        slots.preview(start_ms=0,end_ms=1000,rate_micro_per_second=True)
    with pytest.raises(ValueError):
        slots.preview(start_ms=1,end_ms=1)
    with pytest.raises(ValueError):
        slots.acquire('a',at_ms=-1)


def test_stale_recovery_dry_run_and_idempotency(slot_db):
    slots.acquire('a', at_ms=1000)
    dry = slots.recover_stale_leases(now_ms=3_602_000, older_than_ms=3_600_000)
    assert len(dry['candidates']) == 1 and not dry['recovered_job_ids']
    with slot_db() as c:
        assert c.execute("SELECT state FROM ai_gpu_slot_leases WHERE job_id='a'").fetchone()[0] == 'active'
    recovered = slots.recover_stale_leases(now_ms=3_602_000, older_than_ms=3_600_000, dry_run=False)
    assert recovered['recovered_job_ids'] == ['a']
    assert slots.recover_stale_leases(now_ms=3_602_000, older_than_ms=3_600_000, dry_run=False)['recovered_job_ids'] == []
    with slot_db() as c:
        c.execute("UPDATE ai_compute_jobs SET status='failed' WHERE id='a'")
    assert slots.preview(start_ms=1000,end_ms=3_602_000,rate_micro_per_second=100)['total_micro_eur'] == 0


def test_gpu_opt_in_requires_explicit_kind(monkeypatch):
    monkeypatch.setenv('MTA_AI_GPU_SLOT_TRACKING_ENABLED','true')
    monkeypatch.setenv('MTA_AI_GPU_SLOT_KINDS','demucs, whisper')
    assert slots.slot_enabled_for_kind('demucs')
    assert slots.slot_enabled_for_kind('whisper')
    assert not slots.slot_enabled_for_kind('ace-step')
    monkeypatch.setenv('MTA_AI_GPU_SLOT_TRACKING_ENABLED','false')
    assert not slots.slot_enabled_for_kind('demucs')
