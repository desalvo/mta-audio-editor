"""Immediate, resumable erasure of retired accounts and their retained copies."""
import json
import os
from . import auth, account_lifecycle as life, storage


def erase(uid, actor, *, confirmed=False):
    if confirmed is not True:
        raise ValueError('Confermare la cancellazione definitiva di tutti i dati')
    admin = auth.get_user(actor)
    if not admin or admin['role'] != 'admin' or not admin['active']:
        raise ValueError('Amministratore attivo richiesto')
    with life._LOCK:
        return _erase(uid,actor=actor)


def _erase(uid,*,actor=None):
    journal = life.root() / ('erase-' + str(int(uid)) + '.json')
    if journal.is_symlink():
        raise ValueError('Unsafe erasure journal')
    user = auth.get_user(uid)
    if user and user['role'] == 'admin':
        raise ValueError('Gli amministratori non possono essere eliminati')
    if any(j['state'] in ('queued', 'blocked', 'running') for j in life.jobs(uid)):
        raise ValueError('Attendere la conclusione dei job attivi')
    from .operator_refunds import require_erasure_ready
    from .ai_pull_coordinator import erasure_safe, record_erasure
    with auth.db() as con:
        require_erasure_ready(con,uid)
        erasure_safe(con,uid)
    if journal.exists():
        intent = json.loads(journal.read_text())
        if actor is not None and intent.get('actor')!=actor:
            intent['actor']=actor
            from .storage import _atomic_json_write
            _atomic_json_write(journal,intent)
    else:
        with auth.db() as con:
            life.init(con)
            archives = [dict(r) for r in con.execute('SELECT * FROM account_archives WHERE user_id=?', (uid,))]
        if not archives or (user and (user['active'] or life.info(uid)['state'] not in ('deleted', 'expired'))):
            raise ValueError('Account non presente negli archivi cancellati o riattivato')
        sandbox_ids = []; sandbox_jobs = set(); identities = []
        # Old releases did not persist the owner alongside a sandbox. Inspect
        # the authenticated encrypted payload; never delete another user's box.
        for path in life.root().glob('*.sandbox'):
            if path.is_symlink():
                raise ValueError('Unsafe sandbox')
            data = json.loads(auth._open(path.read_text()))
            if any(r.get('id') == uid for r in data.get('rows', {}).get('users', [])):
                sandbox_ids.append(path.stem)
                for saved in data.get('rows', {}).get('users', []):
                    for kind in ('username','email'):
                        if saved.get(kind): identities.append({'kind':kind,'digest':life.identity(kind,saved[kind])})
                for row in data.get('rows', {}).get('ai_compute_jobs', []):
                    sandbox_jobs.update(v for v in (row.get('id'),row.get('queue_job_id')) if v)
                sandbox_jobs.update(row['job_id'] for row in data.get('queue', []) if row.get('job_id'))
                for row in data.get('billing_outbox', []):
                    sandbox_jobs.update(v for v in (row.get('job_id'),row.get('billing_job_id')) if v)

        with auth.db() as con:
            selected, _ = life._rows_for_user(con, uid)
        intent = {'uid': uid, 'actor':actor, 'archives': [a['id'] for a in archives], 'sandboxes': sandbox_ids,
                  'projects': [p.id for p in storage.list_projects(is_admin=True) if p.owner_user_id == uid],
                  'identities': identities + [{'kind':kind,'digest':life.identity(kind,value)} for a in archives for kind,value in (('username',a['username']),('email',a['email'])) if value],
                  'jobs': sorted(sandbox_jobs | {j['job_id'] for j in life.jobs(uid)} | {r['id'] for r in selected.get('ai_compute_jobs', {}).values()})}
        from .storage import _atomic_json_write
        _atomic_json_write(journal, intent)
        os.chmod(journal, 0o600)
    # Mark first to prevent approval/dispatch while a failed cleanup is retried.
    with auth.db() as con:
        con.execute('BEGIN IMMEDIATE')
        erasure_safe(con,uid)
        current = con.execute('SELECT role,active FROM users WHERE id=?', (uid,)).fetchone()
        if current and (current['role']=='admin' or current['active']):
            journal.unlink(missing_ok=True)
            raise ValueError('Account amministratore o riattivato: cancellazione interrotta')
        con.execute("UPDATE account_lifecycle SET state='erasing' WHERE user_id=?", (uid,))
    for pid in intent['projects']:
        path = storage.ROOT / pid
        if path.is_symlink():
            raise ValueError('Unsafe project directory')
        if path.exists():
            project = storage.load_project(pid)
            if project.owner_user_id != uid:
                raise ValueError('Project owner changed; cleanup stopped')
            storage.delete_project(pid)
            if path.exists():
                raise OSError('Project deletion failed')
        storage.cleanup_session_preview_cache(pid)
    for project in storage.list_projects(is_admin=True):
        if uid in project.shared_with_user_ids:
            project.shared_with_user_ids.remove(uid)
            storage.save_project(project)
    for aid in intent['archives']:
        (life.root() / (aid + '.zip')).unlink(missing_ok=True)
    for sid in intent['sandboxes']:
        (life.root() / (sid + '.sandbox')).unlink(missing_ok=True)
    life._purge_queue(uid, set(intent['jobs']))
    storage.rescan_shared_media(delete_unreferenced=True)
    with auth.db() as con:
        con.execute('BEGIN IMMEDIATE')
        erasure_safe(con,uid)
        protected = con.execute('SELECT role FROM users WHERE id=?', (uid,)).fetchone()
        if protected and protected[0] == 'admin':
            raise ValueError('Gli amministratori non possono essere eliminati')
        selected, meta = life._rows_for_user(con, uid, linked_jobs=intent['jobs'])
        con.execute('PRAGMA secure_delete=ON')
        con.execute('PRAGMA defer_foreign_keys=ON')
        con.execute('UPDATE users SET approved_by=NULL WHERE approved_by=?', (uid,))
        from .subscription_receivables import authorize_account_erasure
        authorize_account_erasure(con,uid,intent.get('actor'))
        from .noncommercial_contributions import authorize_account_erasure as authorize_nc_erasure
        authorize_nc_erasure(con,uid,intent.get('actor'))
        from .worker_cgroup_recovery import authorize_account_erasure as authorize_worker_erasure
        authorize_worker_erasure(con,uid,intent.get('actor'))
        from .worker_loss_resolution import authorize_account_erasure as authorize_loss_erasure
        authorize_loss_erasure(con,uid,intent.get('actor'))
        from .operator_refunds import authorize_account_erasure as authorize_refund_erasure
        authorize_refund_erasure(con,uid,intent.get('actor'))
        record_erasure(con,uid)
        for name, rows in selected.items():
            for key in rows:
                con.execute('DELETE FROM ' + meta[name][0] + ' WHERE rowid=?', (key,))  # noqa: S608 -- quoted SQLite schema
        for table in ('account_archives', 'account_identity_reservations', 'account_audit'):
            con.execute('DELETE FROM ' + table + ' WHERE user_id=?', (uid,))  # noqa: S608 -- fixed table allowlist
        for value in intent.get('identities', []):
            con.execute('DELETE FROM account_identity_reservations WHERE kind=? AND digest=? AND user_id IS NULL', (value['kind'],value['digest']))
        con.execute('DELETE FROM account_audit WHERE actor_id=?', (uid,))
        for sid in intent['sandboxes']:
            con.execute('DELETE FROM account_sandboxes WHERE id=?', (sid,))
        for aid in intent['archives']:
            con.execute('DELETE FROM account_mail_outbox WHERE id=?', ('deleted:' + aid,))
        con.execute('DELETE FROM account_purge_jobs WHERE user_id=?', (uid,))
    journal.unlink()
    return {'done': True}


def resume():
    for journal in life.root().glob('erase-*.json'):
        if journal.is_symlink():
            raise ValueError('Unsafe erasure journal')
        with life._LOCK:
            _erase(int(journal.stem.removeprefix('erase-')))
