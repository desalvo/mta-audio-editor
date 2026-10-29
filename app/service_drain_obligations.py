"""Read-only unfinished-work audit; financial solvency remains a separate gate."""
from contextlib import closing
from pathlib import Path
import sqlite3
import stat


def _read(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError('Unsafe original work journal')
    con = sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=2)
    try:
        con.execute('BEGIN')
        if con.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise ValueError('Work journal integrity unavailable')
        return con
    except BaseException:
        con.close()
        raise


def audit(*, recovering_cutover=None):
    from . import auth, ai_arranger_runtime as queue, storage
    counts = {};reasons = []
    try:
        with closing(_read(auth.db_path())) as con:
            tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if 'account_purge_jobs' in tables:
                counts['account_purge']=con.execute('SELECT COUNT(*) FROM account_purge_jobs').fetchone()[0]
            if 'account_lifecycle' in tables:
                counts['account_archives']=con.execute("SELECT COUNT(*) FROM account_lifecycle WHERE state='deleting'").fetchone()[0]
            for table,sql in (
                ('ai_mail_events',"SELECT COUNT(*) FROM ai_mail_events WHERE state='sending'"),
                ('account_mail_outbox',"SELECT COUNT(*) FROM account_mail_outbox WHERE state='sending'"),
            ):
                if table in tables:
                    # Fixed reviewed table names;age/lease expiry is not proof
                    # that an already dispatched SMTP delivery has stopped.
                    counts[table]=con.execute(sql).fetchone()[0]
            if 'regime_fence_operations' in tables:
                counts['fenced_operations'] = con.execute("SELECT COUNT(*) FROM regime_fence_operations WHERE status!='closed'").fetchone()[0]
            if 'ai_compute_jobs' in tables:
                if {'regime_fence_operations','regime_worker_claims'} <= tables:
                    counts['unverified_workers'] = con.execute('''SELECT COUNT(*) FROM ai_compute_jobs j
                        LEFT JOIN regime_fence_operations f ON f.operation_id='job:ledger:'||j.id
                        LEFT JOIN regime_worker_claims c ON c.operation_id=f.operation_id
                        WHERE j.status NOT IN ('done','failed','cancelled') OR f.status IS NOT 'closed'
                         OR c.state IS NOT 'finished' ''').fetchone()[0]
                else:
                    counts['unverified_workers'] = con.execute('SELECT COUNT(*) FROM ai_compute_jobs').fetchone()[0]
            if 'ai_pull_tasks' in tables:
                counts['pull_execution'] = con.execute("SELECT COUNT(*) FROM ai_pull_tasks WHERE state!='done'").fetchone()[0]
            if 'regime_worker_claims' in tables:
                from .regime_worker_claims import audit_claim_integrity
                if not audit_claim_integrity(con)['safe']:raise ValueError('Original worker claim integrity unavailable')
            if 'ai_gpu_slot_leases' in tables:
                counts['gpu_leases'] = con.execute("SELECT COUNT(*) FROM ai_gpu_slot_leases WHERE state='active'").fetchone()[0]
            if 'regime_admin_cutovers' in tables:
                counts['cutover_recovery'] = con.execute("SELECT COUNT(*) FROM regime_admin_cutovers WHERE phase!='finalized'").fetchone()[0]
                # Recovery may carry exactly its own already committed barrier.
                # A supplied identity alone cannot waive another transition or
                # an inconsistent target epoch, even if all other work is quiet.
                if recovering_cutover is not None:
                    row = con.execute('''SELECT a.id FROM regime_admin_cutovers a
                        JOIN regime_fence_state f ON f.singleton=1
                        WHERE a.id=? AND a.phase='committed' AND f.transitioning=1
                        AND f.regime=a.target AND f.revision=a.source_revision+1''',
                        (recovering_cutover,)).fetchone()
                    if row:
                        counts['cutover_recovery'] -= 1
            if 'regime_payment_outbox' in tables:
                # Provider effects without an original durable terminal receipt
                # require the existing payment recovery; never infer completion.
                columns = {r[1] for r in con.execute('PRAGMA table_info(regime_payment_outbox)')}
                if 'state' not in columns: raise ValueError('Unknown payment intent schema')
                counts['payment_intents'] = con.execute("SELECT COUNT(*) FROM regime_payment_outbox WHERE state NOT IN ('confirmed','cancelled')").fetchone()[0]
        checks = (
            (queue._ROOT/'jobs.sqlite3','queue',"SELECT COUNT(*) FROM jobs j LEFT JOIN terminal_receipts t ON t.job_id=j.job_id WHERE j.state NOT IN ('completed','failed','cancelled') OR t.state IS NOT j.state"),
            (queue._ROOT/'billing-outbox.sqlite3','billing_outbox',"SELECT COUNT(*) FROM deliveries WHERE state!='delivered'"),
            (queue._ROOT/'publication/outbox.sqlite3','publication_outbox',"SELECT COUNT(*) FROM publications WHERE state!='published'"),
        )
        for file,key,sql in checks:
            if file.exists() or file.is_symlink():
                with closing(_read(file)) as con: counts[key] = con.execute(sql).fetchone()[0]
        # Original unfinished filesystem publication/ingest intents predate an
        # activation too. Their absence is never reconstructed from a PID/clock.
        root = Path(storage.ROOT)
        pending = 0
        if root.is_symlink():raise ValueError('Unsafe project root')
        if root.exists():
            for folder in root.iterdir():
                if folder.is_symlink(): raise ValueError('Unverified project journal root')
                if not folder.is_dir() or folder.name.startswith('.'): continue
                for item in folder.iterdir():
                    if item.name.endswith(('.pending.json','-pending.json')):
                        pending += 1
        counts['file_publications'] = pending
        retention=auth.data_root()/'.account-retention'
        if retention.is_symlink():raise ValueError('Unsafe account recovery root')
        counts['account_erasure_recovery']=len(list(retention.glob('erase-*.json'))) if retention.exists() else 0
    except (OSError,sqlite3.Error,ValueError) as exc:
        reasons.append(type(exc).__name__)
    return {'verified':not reasons,'count':sum(counts.values()) if not reasons else None,
            'by_kind':counts,'reasons':reasons,'financial_obligations_certified':False}
