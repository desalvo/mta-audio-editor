#!/usr/bin/env python3
"""Isolated MTA billing acceptance test; never uses production MTA_DATA_DIR."""
import datetime as dt
import json
import os
import sqlite3
import tempfile
from pathlib import Path


def stamp(value):
    return int(dt.datetime.fromisoformat(value).replace(tzinfo=dt.timezone.utc).timestamp())


def main():
    with tempfile.TemporaryDirectory(prefix='mta-billing-acceptance-') as folder:
        root = Path(folder)
        os.environ['MTA_DATA_DIR'] = str(root / 'data')
        os.environ['MTA_AI_USER_STORAGE_ROOT'] = str(root / 'user-storage')
        (root / 'user-storage').mkdir()
        from app import ai_billing
        from app.auth import db
        with db() as c:
            c.execute('CREATE TABLE users(id INTEGER PRIMARY KEY,active INTEGER NOT NULL)')
            c.execute('INSERT INTO users(id,active) VALUES(1,1)')
        start = stamp('2026-10-01T00:00:00')
        finish = stamp('2026-10-02T00:00:00')
        ai_billing.set_price('cpu_seconds', 2000, valid_from=start)
        ai_billing.set_price('disk_gb_hours', 1000, valid_from=start)
        ai_billing.record_persistent_storage(1, 1024**3, sampled_at=start)
        ai_billing.record_persistent_storage(1, 1024**3, sampled_at=finish)
        regular = ai_billing.create_job(1,'acceptance',started_at=start+3600)
        ai_billing.finish_job(regular,'done',{'cpu_seconds':2.0},source='cgroup',finished_at=start+3602)
        diagnostic = ai_billing.create_job(1,'accounting_validation',started_at=start+7200,diagnostic=True)
        ai_billing.finish_job(diagnostic,'done',{'cpu_seconds':3.0},source='cgroup',finished_at=start+7203)
        preview = ai_billing.report('day',user_id=1,anchor='2026-10-01')
        assert preview['diagnostic_jobs']==1, preview
        assert preview['total_micro']==28000, preview
        first = ai_billing.close_period(1,'2026-10-01','2026-10-01')
        second = ai_billing.close_period(1,'2026-10-01','2026-10-01')
        assert first['total_micro']==28000 and not first['already_closed'], first
        assert second['already_closed'] and second['id']==first['id'], second
        integrity = ai_billing.audit_closed_invoices(user_id=1)
        assert integrity['ready'] and integrity['invoice_count']==1, integrity
        try:
            ai_billing.create_job(1,'late',started_at=start+9000)
        except ValueError:
            late_rejected=True
        else:
            raise AssertionError('Closed-period job insertion was allowed')
        output={'isolated':True,'cpu_micro_eur':4000,'storage_micro_eur':24000,'total_micro_eur':first['total_micro'],'diagnostic_jobs':preview['diagnostic_jobs'],'first_close':first,'repeat_close':second,'audit':integrity,'late_job_rejected':late_rejected}
        print(json.dumps(output,indent=2))


if __name__=='__main__':
    main()
