#!/usr/bin/env python3
"""MTA r207 billing recovery validation with a disposable SQLite database.

Run with PYTHONPATH=/opt/mta/application /opt/mta/venv-mta/bin/python <script>.
Never points at the production SQLite database.
"""
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def utc(s):
    return int(datetime.fromisoformat(s).replace(tzinfo=timezone.utc).timestamp())


def main():
    # Import after isolating all persistent application paths.
    with tempfile.TemporaryDirectory(prefix="mta-recovery-cert-") as tmp:
        os.environ["MTA_DATA_DIR"] = tmp
        os.environ.pop("MTA_AI_USER_STORAGE_ROOT", None)
        from app import auth, ai_billing

        auth.DATA_ROOT = Path(tmp)
        auth.init_auth_db()
        now = utc("2026-10-12T12:00:00")
        with auth.db() as c:
            c.execute(
                "INSERT INTO users(id, username, email, password_hash, role, active, "
                "email_confirmed, created_at, updated_at) "
                "VALUES(1, 'recovery_test', 'recovery@example.invalid', 'test-only', "
                "'user', 1, 1, ?, ?)",
                (now, now),
            )
        completed = ai_billing.create_job(1, "recovery_completed", started_at=utc("2026-10-10T09:00:00"))
        ai_billing.finish_job(completed, "done", {"cpu_seconds": 2.0}, source="cgroup", finished_at=utc("2026-10-10T09:05:00"))
        orphan = ai_billing.create_job(1, "recovery_orphan", started_at=utc("2026-10-10T11:00:00"))
        recent = ai_billing.create_job(1, "recovery_recent", started_at=now - 600)

        before = {j: _job(auth, j) for j in (completed, orphan, recent)}
        dry = ai_billing.recover_stale_jobs(now=now, older_than_seconds=3600, dry_run=True)
        if not ([j["job_id"] for j in dry["candidates"]] == [orphan]):raise AssertionError(dry)
        if not (dry["recovered_job_ids"] == []):raise AssertionError(dry)
        if not ({j: _job(auth, j) for j in before} == before):raise AssertionError("dry-run altered database")
        recovered = ai_billing.recover_stale_jobs(now=now, older_than_seconds=3600, dry_run=False)
        if not (recovered["recovered_job_ids"] == [orphan]):raise AssertionError(recovered)
        orphan_row = _job(auth, orphan)
        if not (orphan_row["status"] == "failed"):raise AssertionError('Required validation failed')
        if not (orphan_row["resource_source"] == "unmetered"):raise AssertionError('Required validation failed')
        if not (json.loads(orphan_row["usage_json"]) == {}):raise AssertionError('Required validation failed')
        if not (_job(auth, recent)["status"] == "running"):raise AssertionError('Required validation failed')
        if not (_job(auth, completed)["status"] == "done"):raise AssertionError('Required validation failed')
        repeat = ai_billing.recover_stale_jobs(now=now, older_than_seconds=3600, dry_run=False)
        if not (repeat["recovered_job_ids"] == []):raise AssertionError(repeat)
        closed_rejected = False
        try:
            ai_billing.close_period(1, "2026-10-10", "2026-10-10")
        except ValueError:
            closed_rejected = True
        if not (closed_rejected):raise AssertionError("Failed orphan was unexpectedly billable")
        with auth.db() as c:
            count = c.execute("SELECT count(*) FROM ai_billing_periods").fetchone()[0]
        if not (count == 0):raise AssertionError('Required validation failed')
        print(json.dumps({
            "isolated": True,
            "dry_run_candidates": len(dry["candidates"]),
            "dry_run_database_unchanged": True,
            "recovered_job_ids": recovered["recovered_job_ids"],
            "orphan_status": orphan_row["status"],
            "orphan_source": orphan_row["resource_source"],
            "orphan_usage": json.loads(orphan_row["usage_json"]),
            "recent_job_untouched": True,
            "completed_job_untouched": True,
            "repeat_recovery_ids": repeat["recovered_job_ids"],
            "billing_close_rejected": closed_rejected,
            "closed_periods": count,
        }, indent=2))


def _job(auth, job_id):
    with auth.db() as c:
        row = c.execute("SELECT status, resource_source, usage_json, finished_at FROM ai_compute_jobs WHERE id=?", (job_id,)).fetchone()
        return dict(row)


if __name__ == "__main__":
    main()
