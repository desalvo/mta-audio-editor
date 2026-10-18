"""Portable administrator snapshots and an offline, empty-target restore.

Archives contain credentials. They are streamed to the administrator, never
published or retained as a second application copy of deleted user data.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import stat
import tempfile
import threading
import time
import zipfile
from contextlib import contextmanager, closing
from . import auth, storage, account_lifecycle as life, ai_arranger_runtime as queue
from .version import APP_RELEASE

SCHEMA = 'mta/application-dump/v1'
_CONDITION = threading.Condition()
_ACTIVE = 0
_BUSY = False
MAX_FILES = 200000


def limit():
    return max(1024 * 1024, min(int(os.getenv('MTA_ADMIN_DUMP_MAX_BYTES', str(100 * 1024**3))), 1024**4))


def enter_request():
    global _ACTIVE
    with _CONDITION:
        if _BUSY:
            return False
        _ACTIVE += 1
        return True


def leave_request():
    global _ACTIVE
    with _CONDITION:
        _ACTIVE -= 1
        _CONDITION.notify_all()


@contextmanager
def maintenance():
    global _BUSY
    with _CONDITION:
        if _BUSY:
            raise ValueError('Dump già in corso')
        _BUSY = True
        try:
            if not _CONDITION.wait_for(lambda: _ACTIVE <= 1, timeout=30):
                raise ValueError('Richieste ancora attive: riprovare')
        except BaseException:
            _BUSY = False
            raise
    try:
        with life._LOCK:
            with queue._db() as con:
                if con.execute("SELECT 1 FROM jobs WHERE state IN ('queued','running','blocked') LIMIT 1").fetchone():
                    raise ValueError('Annullare o completare tutti i job AI prima del dump')
            if any(life.root().glob('erase-*.json')):
                raise ValueError('Completare prima le cancellazioni definitive interrotte')
            yield
    finally:
        with _CONDITION:
            _BUSY = False
            _CONDITION.notify_all()


def catalog():
    with auth.db() as con:
        life.init(con)
        users = [dict(r) for r in con.execute('SELECT id,username,display_name,role,active FROM users ORDER BY username COLLATE NOCASE')]
        known = {u['id'] for u in users}
        users += [dict(id=r['user_id'], username=r['username'] or 'Account rimosso', display_name='', role='user', active=0)
                  for r in con.execute('SELECT DISTINCT user_id,username FROM account_archives') if r['user_id'] not in known]
    return {'users': users, 'projects': [{'id': p.id, 'title': p.title, 'owner_user_id': p.owner_user_id} for p in storage.list_projects(is_admin=True)],
            'max_bytes': limit(), 'restore_mode': 'offline-empty-target', 'includes': 'Configurazione, chiavi, accounting e cronologia dei soli utenti inclusi; account admin sempre inclusi. Modelli e cache ricreabili esclusi.'}


def selection(body):
    if not isinstance(body, dict) or set(body) - {'all_users', 'all_projects', 'user_ids', 'project_ids'}:
        raise ValueError('Selezione non valida')
    for key in ('all_users', 'all_projects'):
        if type(body.get(key, False)) is not bool:
            raise ValueError('Selezione non valida')
    for key, typ in (('user_ids', int), ('project_ids', str)):
        values = body.get(key, [])
        if not isinstance(values, list) or len(values) > 10000 or any(type(v) is not typ for v in values):
            raise ValueError('Selezione non valida')
    data = catalog()
    all_users = {u['id'] for u in data['users']}
    all_projects = {p['id'] for p in data['projects']}
    if set(body.get('user_ids', [])) - all_users or set(body.get('project_ids', [])) - all_projects:
        raise ValueError('Utente o progetto non più disponibile: aggiornare la selezione')
    chosen = all_users if body.get('all_users') else set(body.get('user_ids', []))
    pids = all_projects if body.get('all_projects') else set(body.get('project_ids', []))
    pids |= {p['id'] for p in data['projects'] if p['owner_user_id'] in chosen}
    owners = {p['owner_user_id'] for p in data['projects'] if p['id'] in pids} - {None}
    uids = chosen | owners | {u['id'] for u in data['users'] if u['role'] == 'admin'}
    return data, uids, pids


def _snapshot(source, target):
    if source.is_symlink() or not source.is_file():
        raise ValueError('Database non regolare')
    with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as src, closing(sqlite3.connect(target)) as dst:
        src.backup(dst)


def _filter_auth(path, uids, pids, all_ids):
    with closing(sqlite3.connect(path)) as con:
        con.row_factory = sqlite3.Row
        con.execute('PRAGMA foreign_keys=OFF')
        for uid in all_ids - uids:
            selected, meta = life._rows_for_user(con, uid)
            con.execute('UPDATE users SET approved_by=NULL WHERE approved_by=?', (uid,))
            for name, rows in selected.items():
                for key in rows:
                    con.execute('DELETE FROM ' + meta[name][0] + ' WHERE rowid=?', (key,))  # noqa: S608 -- quoted schema
            for table in ('account_identity_reservations', 'account_archives', 'account_audit'):
                con.execute('DELETE FROM ' + table + ' WHERE user_id=?', (uid,))  # noqa: S608 -- fixed tables
        for trigger, in con.execute("SELECT name FROM sqlite_master WHERE type='trigger'").fetchall():
            con.execute('DROP TRIGGER "' + trigger.replace('"','""') + '"')
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        # Recovery ZIPs may contain more projects than the explicit selection.
        for row in con.execute('SELECT id,user_id,project_ids FROM account_archives').fetchall():
            if row['user_id'] not in uids or not set(json.loads(row['project_ids'])).issubset(pids):
                con.execute('DELETE FROM account_mail_outbox WHERE id=?', ('deleted:' + row['id'],))
                con.execute('DELETE FROM account_archives WHERE id=?', (row['id'],))
        if all_ids - uids:
            con.execute('DELETE FROM account_identity_reservations WHERE user_id IS NULL')
        # Authentication challenges are transient and must not be resurrected.
        for table in ('sessions', 'email_tokens', 'oauth_nonces', 'social_totp_challenges', 'account_email_mfa', 'account_action_confirmations'):
            if table in tables:
                con.execute('DELETE FROM "' + table + '"')  # noqa: S608 -- fixed allowlist
        con.commit()
        con.execute('VACUUM')


def create(body):
    with maintenance():
        data, uids, pids = selection(body)
        # Keep the central ledger unchanged while copying its separate delivery
        # outbox: an applied acknowledgement must never outlive an older ledger
        # snapshot. Readers remain possible; background writers retry afterward.
        with auth.db() as frozen:
            frozen.execute('BEGIN IMMEDIATE')
            return _create_snapshot(data, uids, pids)


def _create_snapshot(data, uids, pids):
    with tempfile.TemporaryDirectory(prefix='mta-dump-stage-') as folder:
        stage = Path(folder)
        _snapshot(auth.db_path(), stage / 'auth.sqlite3')
        _filter_auth(stage / 'auth.sqlite3', uids, pids, {u['id'] for u in data['users']})
        _snapshot((queue._ROOT / 'jobs.sqlite3').absolute(), stage / 'jobs.sqlite3')
        with closing(sqlite3.connect(stage / 'jobs.sqlite3')) as con:
            con.row_factory = sqlite3.Row
            kept = set()
            for row in con.execute('SELECT job_id,actor_user_id,payload_json FROM jobs').fetchall():
                owner = row['actor_user_id']
                if owner is None:
                    try: owner = json.loads(row['payload_json'] or '{}').get('actor_user_id')
                    except ValueError: owner = None
                if owner in uids:
                    kept.add(row['job_id'])
                else:
                    con.execute('DELETE FROM jobs WHERE job_id=?', (row['job_id'],))
            for table in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall():
                quoted = '"' + table[0].replace('"', '""') + '"'
                if 'job_id' in {r[1] for r in con.execute('PRAGMA table_info(' + quoted + ')')}:
                    for row in con.execute('SELECT rowid,job_id FROM ' + quoted).fetchall():  # noqa: S608 -- SQLite schema
                        if row['job_id'] not in kept:
                            con.execute('DELETE FROM ' + quoted + ' WHERE rowid=?', (row['rowid'],))  # noqa: S608
            con.commit(); con.execute('VACUUM')
        # Export only settled outbox entries for included jobs, never pending work.
        files = {'data/auth.sqlite3': stage / 'auth.sqlite3', 'queue/jobs.sqlite3': stage / 'jobs.sqlite3', 'data/.auth-secret': auth.secret_path()}
        outbox = queue._ROOT / 'billing-outbox.sqlite3'
        if outbox.is_file():
            _snapshot(outbox.absolute(), stage / 'billing-outbox.sqlite3')
            with closing(sqlite3.connect(stage / 'billing-outbox.sqlite3')) as con:
                for jid, in con.execute('SELECT job_id FROM deliveries').fetchall():
                    if jid not in kept:
                        con.execute('DELETE FROM deliveries WHERE job_id=?', (jid,))
                con.commit(); con.execute('VACUUM')
            files['queue/billing-outbox.sqlite3'] = stage / 'billing-outbox.sqlite3'
        publications = queue._ROOT / 'publication/outbox.sqlite3'
        if publications.is_file():
            _snapshot(publications.absolute(), stage / 'publication.sqlite3')
            with closing(sqlite3.connect(stage / 'publication.sqlite3')) as con:
                for jid, pid in con.execute('SELECT job_id,project_id FROM publications').fetchall():
                    if jid not in kept or pid not in pids:
                        con.execute('DELETE FROM publications WHERE job_id=?', (jid,))
                    else:
                        audio = publications.parent / (jid + '.wav')
                        if audio.exists(): files['queue/publication/' + audio.name] = audio
                con.commit(); con.execute('VACUUM')
            files['queue/publication/outbox.sqlite3'] = stage / 'publication.sqlite3'
        from . import ai_result_cache
        cache = ai_result_cache._root()
        if cache:
            with closing(sqlite3.connect(stage / 'auth.sqlite3')) as con:
                linked = {r[0] for r in con.execute('SELECT id FROM ai_compute_jobs')} | kept
            for metadata in cache.glob('*.json'):
                if metadata.is_symlink() or metadata.stat().st_size > 1024**2: raise ValueError('Unsafe result metadata')
                details = json.loads(metadata.read_text())
                if details.get('job_id') in linked and details.get('expires_at', 0) > time.time():
                    blob = metadata.with_suffix('.bin')
                    with ai_result_cache._entry_lock(cache, blob):
                        if blob.is_symlink() or not blob.is_file(): raise ValueError('Unsafe result artifact')
                        for entry in (metadata, blob):
                            target = stage / entry.name
                            shutil.copyfile(entry, target)
                            files['data/.ai-result-cache/' + entry.name] = target
        with closing(sqlite3.connect(stage / 'auth.sqlite3')) as con:
            archive_ids = {r[0] for r in con.execute('SELECT id FROM account_archives')}
            boxes = {r[0] for r in con.execute('SELECT id FROM account_sandboxes')}
        keep_boxes = set()
        for sid in boxes:
            path = life.root() / (sid + '.sandbox')
            if path.is_symlink(): raise ValueError('Unsafe sandbox')
            if path.exists():
                payload = json.loads(auth._open(path.read_text()))
                if all(r['id'] in uids for r in payload.get('rows', {}).get('users', [])):
                    files['data/.account-retention/' + path.name] = path; keep_boxes.add(sid)
        with closing(sqlite3.connect(stage / 'auth.sqlite3')) as con:
            for sid in boxes - keep_boxes:
                con.execute('DELETE FROM account_sandboxes WHERE id=?', (sid,))
            con.commit(); con.execute('VACUUM')
        for aid in archive_ids:
            path = life.root() / (aid + '.zip')
            if path.exists(): files['data/.account-retention/' + path.name] = path
        for pid in sorted(pids):
            base = storage.ROOT / pid
            if base.is_symlink(): raise ValueError('Unsafe project')
            for path in sorted(base.rglob('*')):
                if path.is_symlink(): raise ValueError('Project symlinks are not portable')
                if path.is_file() and '.preview' not in path.relative_to(base).parts and not path.name.endswith('.tmp'):
                    files['projects/' + pid + '/' + path.relative_to(base).as_posix()] = path
            metadata_name = 'projects/' + pid + '/project.json'
            if metadata_name in files:
                project_data = json.loads(files[metadata_name].read_text())
                project_data['shared_with_user_ids'] = [uid for uid in project_data.get('shared_with_user_ids', []) if uid in uids]
                copy = stage / (pid + '.project.json')
                copy.write_text(json.dumps(project_data, ensure_ascii=False))
                files[metadata_name] = copy
        # Portable app settings are in auth.sqlite3. Environment is reference
        # data only: restore never executes commands or applies external paths.
        (stage / 'environment.json').write_text(json.dumps({k: v for k, v in os.environ.items() if k.startswith('MTA_')}, indent=2))
        files['reference/operator-environment.json'] = stage / 'environment.json'
        from . import diagnostic_bundle, model_updater
        for label, source in (
            ('data/.diagnostics/enabled.json', diagnostic_bundle.BASE/'enabled.json'),
            ('data/.model-settings/blacklist.json', model_updater.BLACKLIST_FILE),
            ('data/.model-settings/catalog.json', model_updater.CATALOG_FILE),
        ):
            if source.exists(): files[label] = source
        from .ai_gpu_verified import root as gpu_root
        for name in ('key', 'policy.json'):
            path = gpu_root() / name
            if path.exists(): files['gpu/' + name] = path
        fd, name = tempfile.mkstemp(prefix='mta-application-dump-', suffix='.zip'); os.close(fd)
        output = Path(name)
        try:
            manifest = {'schema': SCHEMA, 'release': APP_RELEASE, 'created_at': int(time.time()), 'user_ids': sorted(uids), 'project_ids': sorted(pids), 'entries': {},
                        'restore': 'offline-empty-target', 'exclusions': ['installed software and AI models', 'regenerable previews and model caches', 'active sessions and login challenges', 'OS/service configuration (environment reference included)']}
            total = 0
            if len(files) > MAX_FILES: raise ValueError('Troppi file')
            with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
                for key, path in files.items():
                    if path.is_symlink() or not path.is_file(): raise ValueError('Unsafe dump source')
                    digest = hashlib.sha256(); size = 0
                    with path.open('rb') as src, archive.open(key, 'w', force_zip64=True) as dst:
                        while chunk := src.read(1024 * 1024):
                            total += len(chunk); size += len(chunk)
                            if total > limit(): raise ValueError('Dump superiore al limite configurato')
                            digest.update(chunk); dst.write(chunk)
                    manifest['entries'][key] = {'bytes': size, 'sha256': digest.hexdigest()}
                archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
            inspect(output)
            return output
        except BaseException:
            output.unlink(missing_ok=True)
            raise


def _safe_name(name):
    p = PurePosixPath(name)
    if not name or '\\' in name or '\x00' in name or p.is_absolute() or any(x in ('', '.', '..') for x in name.split('/')) or ':' in name:
        raise ValueError('Unsafe dump path')
    parts = p.parts
    valid = (name in ('data/auth.sqlite3', 'data/.auth-secret', 'queue/jobs.sqlite3', 'queue/billing-outbox.sqlite3', 'gpu/key', 'gpu/policy.json', 'reference/operator-environment.json', 'data/.diagnostics/enabled.json', 'data/.model-settings/blacklist.json', 'data/.model-settings/catalog.json')
             or len(parts) == 3 and parts[:2] == ('data', '.account-retention') and parts[2].split('.')[0].isalnum() and parts[2].endswith(('.zip', '.sandbox'))
             or len(parts) == 3 and parts[:2] == ('data', '.ai-result-cache') and len(parts[2].split('.')[0]) == 64 and all(c in '0123456789abcdef' for c in parts[2].split('.')[0]) and parts[2].endswith(('.json', '.bin'))
             or name == 'queue/publication/outbox.sqlite3'
             or len(parts) == 3 and parts[:2] == ('queue', 'publication') and parts[2].endswith('.wav') and queue._SAFE_JOB_ID.fullmatch(parts[2][:-4])
             or len(parts) >= 3 and parts[0] == 'projects' and storage.PID_RE.fullmatch(parts[1]))
    if not valid: raise ValueError('Unknown dump path')


def inspect(path, *, stage=None):
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) > MAX_FILES + 1 or len({e.filename.casefold() for e in entries}) != len(entries): raise ValueError('Duplicate or excessive entries')
        try:
            info = archive.getinfo('manifest.json')
            if info.file_size > 16 * 1024**2: raise ValueError('Manifest too large')
            manifest = json.loads(archive.read(info))
        except (KeyError, json.JSONDecodeError) as exc: raise ValueError('Invalid dump manifest') from exc
        if not isinstance(manifest, dict) or manifest.get('schema') != SCHEMA or manifest.get('release') != APP_RELEASE or not isinstance(manifest.get('entries'), dict): raise ValueError('Unsupported dump format/release')
        if (not isinstance(manifest.get('user_ids'), list) or any(type(u) is not int or u <= 0 for u in manifest['user_ids'])
                or not isinstance(manifest.get('project_ids'), list) or any(not isinstance(p, str) or not storage.PID_RE.fullmatch(p) for p in manifest['project_ids'])):
            raise ValueError('Invalid selection manifest')
        records = manifest['entries']
        if set(records) != {e.filename for e in entries} - {'manifest.json'} or not {'data/auth.sqlite3', 'data/.auth-secret', 'queue/jobs.sqlite3'} <= set(records): raise ValueError('Incomplete dump')
        total = 0
        for entry in entries:
            if entry.filename == 'manifest.json': continue
            _safe_name(entry.filename)
            mode = entry.external_attr >> 16
            if entry.is_dir() or stat.S_ISLNK(mode) or entry.flag_bits & 1 or stat.S_IFMT(mode) not in (0, stat.S_IFREG): raise ValueError('Non-regular dump entry')
            meta = records[entry.filename]
            if not isinstance(meta, dict) or meta.get('bytes') != entry.file_size: raise ValueError('Invalid dump size')
            total += entry.file_size
            if total > limit(): raise ValueError('Dump exceeds configured limit')
            digest = hashlib.sha256()
            destination = None
            if stage is not None:
                destination = Path(stage) / entry.filename
                destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with archive.open(entry) as src:
                out = destination.open('xb') if destination else None
                try:
                    actual = 0
                    while chunk := src.read(1024 * 1024):
                        actual += len(chunk)
                        if actual > entry.file_size: raise ValueError('Oversized entry')
                        digest.update(chunk)
                        if out: out.write(chunk)
                finally:
                    if out: out.close(); os.chmod(destination, 0o600)
            if digest.hexdigest() != meta.get('sha256') or actual != entry.file_size: raise ValueError('Dump checksum mismatch')
        return manifest


def _validate_database(path):
    with closing(sqlite3.connect(path)) as con:
        if con.execute("SELECT 1 FROM sqlite_master WHERE type IN ('trigger','view') OR lower(sql) LIKE '%virtual table%'").fetchone():
            raise ValueError('Executable database schema not supported')
        if con.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or con.execute('PRAGMA foreign_key_check').fetchone():
            raise ValueError('Invalid restore database')


def restore(path, *, data_dir, queue_dir, gpu_dir, service_stopped=False):
    """Publish validated content into empty roots; never replace live accounts.

    Target roots must be disjoint; data and project roots are intentionally
    co-located, matching MTA_DATA_DIR. Roll back every published root on error.
    """
    if service_stopped is not True: raise ValueError('Arrestare il servizio e confermare --service-stopped')
    roots = [Path(p).absolute() for p in (data_dir, queue_dir, gpu_dir)]
    for root in roots:
        if root.is_symlink() or any(p.is_symlink() for p in root.parents): raise ValueError('Unsafe restore target')
        if root.exists() and (not root.is_dir() or any(root.iterdir())): raise ValueError('Restore requires empty directories; existing accounts and admins are never replaced')
    if any(a == b or a in b.parents or b in a.parents for i, a in enumerate(roots) for b in roots[i + 1:]): raise ValueError('Overlapping restore targets')
    stages = []; published = []
    try:
        for root in roots:
            root.parent.mkdir(parents=True, exist_ok=True)
            stages.append(Path(tempfile.mkdtemp(prefix='.mta-restore-', dir=root.parent)))
        with tempfile.TemporaryDirectory(prefix='mta-restore-validate-') as folder:
            manifest = inspect(path, stage=folder)
            source = Path(folder)
            for relative in ('data/auth.sqlite3','queue/jobs.sqlite3','queue/billing-outbox.sqlite3','queue/publication/outbox.sqlite3'):
                if (source / relative).exists(): _validate_database(source / relative)
            database = source / 'data/auth.sqlite3'
            with closing(sqlite3.connect(database)) as con:
                if con.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or con.execute('PRAGMA foreign_key_check').fetchone(): raise ValueError('Invalid authentication database')
                if not con.execute("SELECT 1 FROM users WHERE role='admin' AND active=1 AND email_confirmed=1").fetchone(): raise ValueError('No active administrator in dump')
                if any(row[0] not in manifest['user_ids'] for row in con.execute('SELECT id FROM users')): raise ValueError('Unselected account in dump')
                for table in ('account_archives','account_sandboxes'):
                    for row in con.execute('SELECT id FROM ' + table):  # noqa: S608 -- fixed table allowlist
                        if not re.fullmatch('[a-f0-9]{32}', row[0]): raise ValueError('Unsafe retained archive identity')
                for project_ids, in con.execute('SELECT project_ids FROM account_archives'):
                    values = json.loads(project_ids)
                    if not isinstance(values,list) or any(not isinstance(p,str) or not storage.PID_RE.fullmatch(p) for p in values): raise ValueError('Unsafe retained project identity')

            with closing(sqlite3.connect(source / 'queue/jobs.sqlite3')) as con:
                if con.execute('PRAGMA integrity_check').fetchone()[0] != 'ok': raise ValueError('Invalid queue database')
                if con.execute("SELECT 1 FROM jobs WHERE state IN ('queued','running','blocked')").fetchone(): raise ValueError('Dump contains active jobs')
            if (source / 'data/.auth-secret').stat().st_size != 32: raise ValueError('Invalid authentication key')
            found_projects = set()
            for entry in (source / 'projects').iterdir() if (source / 'projects').exists() else []:
                value = json.loads((entry / 'project.json').read_text())
                if value.get('id') != entry.name or entry.name not in manifest['project_ids'] or value.get('owner_user_id') is not None and value['owner_user_id'] not in manifest['user_ids']: raise ValueError('Invalid project identity')
                from .models import Project
                Project.model_validate(value)
                found_projects.add(entry.name)
            if found_projects != set(manifest['project_ids']): raise ValueError('Missing project data')
            for name in ('data', 'projects'):
                if (source / name).exists(): shutil.copytree(source / name, stages[0], dirs_exist_ok=True)
            for name, dest in (('queue', stages[1]), ('gpu', stages[2])):
                if (source / name).exists(): shutil.copytree(source / name, dest, dirs_exist_ok=True)
            if (source / 'reference').exists(): shutil.copytree(source / 'reference', stages[0] / '.restore-reference')
        for root, stage in zip(roots, stages):
            if root.exists(): root.rmdir()
            os.replace(stage, root); published.append(root)
        return {'done': True, 'projects': len(manifest['project_ids']), 'users': len(manifest['user_ids'])}
    except BaseException:
        for root in reversed(published): shutil.rmtree(root)
        raise
    finally:
        for stage in stages:
            if stage.exists(): shutil.rmtree(stage)
