"""Optional durable *planning-only* journal. No inference is executed or billed.

Set MTA_AI_PLANNING_DB to an absolute local SQLite filename to opt in.
The existing volatile queue remains the default.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import os
import stat
from pathlib import Path
import sqlite3
from uuid import uuid4

from .ai_job_queue import MAX_JOBS, MAX_PLAN_BYTES, TERMINAL, _safe_plan


class SQLitePlanningQueue:
    def __init__(self, path: str | os.PathLike[str]):
        path = Path(path)
        if not path.is_absolute():
            raise ValueError('planning database path must be absolute')
        # Never traverse symbolic links in the directory tree, including ancestors.
        self._check_path(path, check_file=False)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._check_path(path)
        self.path = str(path)
        with self._connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS planning_jobs (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                id TEXT NOT NULL UNIQUE, project_id TEXT NOT NULL,
                owner_id TEXT NOT NULL, status TEXT NOT NULL,
                payload TEXT NOT NULL)''')
            columns = {row[1]: row[2].upper() for row in db.execute('PRAGMA table_info(planning_jobs)')}
            required = {'seq': 'INTEGER', 'id': 'TEXT', 'project_id': 'TEXT',
                        'owner_id': 'TEXT', 'status': 'TEXT', 'payload': 'TEXT'}
            if any(columns.get(name) != typ for name, typ in required.items()):
                raise ValueError('incompatible planning database schema')
            if db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise ValueError('planning database integrity check failed')
            db.execute('CREATE INDEX IF NOT EXISTS planning_owner_idx ON planning_jobs(project_id, owner_id, status, seq)')
        # Bind the journal instance to the file initialized above. An unrelated
        # regular SQLite database must not silently replace it later.
        identity = Path(self.path).stat()
        self._database_identity = (identity.st_dev, identity.st_ino)

    @staticmethod
    def _check_path(path: Path, *, check_file: bool = True):
        for parent in (path.parent, *path.parent.parents):
            try:
                mode = parent.lstat().st_mode
            except FileNotFoundError:
                continue
            if not stat.S_ISDIR(mode):
                raise ValueError('planning database ancestor must be a real directory')
        if check_file:
            try:
                mode = path.lstat().st_mode
            except FileNotFoundError:
                pass
            else:
                if not stat.S_ISREG(mode):
                    raise ValueError('planning database must be a regular file')
            for suffix in ('-wal', '-shm', '-journal'):
                sidecar = Path(str(path) + suffix)
                try:
                    mode = sidecar.lstat().st_mode
                except FileNotFoundError:
                    continue
                if not stat.S_ISREG(mode):
                    raise ValueError('planning database sidecar must be a regular file')

    def _connect(self):
        path = Path(self.path)
        self._check_path(path)
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        try:
            self._check_path(path)
            db.execute('PRAGMA busy_timeout=10000')
            # Refuse a swapped database file after connect, rather than writing
            # through a stale handle or to a substituted pathname.
            expected = path.stat()
            opened = db.execute('PRAGMA database_list').fetchone()
            actual = Path(opened[2]).stat()
            if (expected.st_dev, expected.st_ino) != (actual.st_dev, actual.st_ino):
                raise ValueError('planning database path changed')
            pinned = getattr(self, '_database_identity', None)
            if pinned is not None and (expected.st_dev, expected.st_ino) != pinned:
                raise ValueError('planning database was replaced after initialization')
        except BaseException:
            db.close()
            raise
        return db

    @staticmethod
    def _decode(row, *, job_id=None, project_id=None, owner_id=None, status=None):
        if row is None:
            return None
        payload = row[0]
        if not isinstance(payload, str) or len(payload.encode('utf-8')) > MAX_PLAN_BYTES + 4096:
            raise ValueError('invalid persisted planning payload size')
        try:
            item = json.loads(payload, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('non-finite value')))
        except (TypeError, json.JSONDecodeError, ValueError) as exc:
            raise ValueError('corrupt persisted planning payload') from exc
        if (not isinstance(item, dict) or item.get('operation') not in ('remix', 'rearrange')
                or item.get('generation_available') is not False or not isinstance(item.get('plan'), dict)
                or item.get('status') not in ('planned', 'cancelled', 'completed', 'failed')):
            raise ValueError('invalid persisted planning record')
        for key, expected in (('id', job_id), ('project_id', project_id),
                              ('owner_id', owner_id), ('status', status)):
            if expected is not None and item.get(key) != expected:
                raise ValueError('planning database record identity mismatch')
        _safe_plan(item['plan'])
        return item

    def submit(self, project_id: str, owner_id: str, operation: str, plan: dict) -> dict:
        if operation not in ('remix', 'rearrange'):
            raise ValueError('unsupported AI operation')
        if not isinstance(project_id, str) or not project_id.strip():
            raise ValueError('project identifier is required')
        if not isinstance(owner_id, str) or not owner_id.strip():
            raise ValueError('owner identifier is required')
        plan = _safe_plan(plan)
        item = {'id': uuid4().hex, 'project_id': project_id, 'owner_id': owner_id,
                'operation': operation, 'status': 'planned', 'generation_available': False,
                'created_at': datetime.now(timezone.utc).isoformat(), 'plan': plan,
                'message': 'Plan ready. No verified inference worker configured.'}
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                count = db.execute('SELECT count(*) FROM planning_jobs').fetchone()[0]
                if count >= MAX_JOBS:
                    # A row whose indexed state was forged to look non-terminal
                    # must not escape validation during capacity eviction.
                    for stored in db.execute('SELECT payload,id,project_id,owner_id,status FROM planning_jobs'):
                        self._decode((stored[0],), job_id=stored[1],
                                     project_id=stored[2], owner_id=stored[3], status=stored[4])
                    old = db.execute("SELECT seq, payload, id, project_id, owner_id, status FROM planning_jobs WHERE status IN ('cancelled','completed','failed') ORDER BY seq LIMIT 1").fetchone()
                    if not old:
                        raise ValueError('AI planning queue at capacity')
                    # Never silently discard a damaged journal entry to make room.
                    self._decode((old[1],), job_id=old[2], project_id=old[3],
                                 owner_id=old[4], status=old[5])
                    db.execute('DELETE FROM planning_jobs WHERE seq=?', (old[0],))
                db.execute('INSERT INTO planning_jobs(id,project_id,owner_id,status,payload) VALUES (?,?,?,?,?)',
                           (item['id'], project_id, owner_id, 'planned', json.dumps(item, allow_nan=False)))
                db.execute('COMMIT')
            except BaseException:
                db.execute('ROLLBACK')
                raise
        return deepcopy(item)

    def _audit_owner_records(self, db, project_id: str, owner_id: str):
        """Validate all visible entries before serving a partial page or lookup.

        A forged status or malformed record outside the requested page must not
        be silently hidden by pagination or status filtering.
        """
        rows = db.execute(
            'SELECT payload,id,project_id,owner_id,status FROM planning_jobs '
            'WHERE project_id=? AND owner_id=?', (project_id, owner_id)
        )
        for payload, jid, pid, oid, state in rows:
            self._decode((payload,), job_id=jid, project_id=pid,
                         owner_id=oid, status=state)

    def get(self, job_id: str, project_id: str, owner_id: str) -> dict | None:
        # Audit and lookup must observe the same SQLite snapshot. Without BEGIN,
        # a concurrent writer can alter a row between those separate SELECTs.
        with self._connect() as db:
            db.execute('BEGIN')
            try:
                self._audit_owner_records(db, project_id, owner_id)
                row = db.execute(
                    'SELECT payload, status FROM planning_jobs '
                    'WHERE id=? AND project_id=? AND owner_id=?',
                    (job_id, project_id, owner_id),
                ).fetchone()
                item = self._decode(row, job_id=job_id, project_id=project_id,
                                    owner_id=owner_id, status=row[1] if row else None)
                db.execute('COMMIT')
            except BaseException:
                db.execute('ROLLBACK')
                raise
        return item

    def list(self, project_id: str, owner_id: str, *, limit: int = 20,
             offset: int = 0, status: str | None = None) -> dict:
        if not isinstance(project_id, str) or not project_id.strip():
            raise ValueError('project identifier is required')
        if not isinstance(owner_id, str) or not owner_id.strip():
            raise ValueError('owner identifier is required')
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('limit must be between 1 and 100')
        if type(offset) is not int or not 0 <= offset <= MAX_JOBS:
            raise ValueError('invalid pagination offset')
        if status is not None and status not in ('planned', 'cancelled', 'completed', 'failed'):
            raise ValueError('invalid status filter')
        where = 'project_id=? AND owner_id=?'
        params: tuple = (project_id, owner_id)
        if status is not None:
            where += ' AND status=?'
            params += (status,)
        with self._connect() as db:
            db.execute('BEGIN')
            try:
                self._audit_owner_records(db, project_id, owner_id)
                total = db.execute('SELECT count(*) FROM planning_jobs WHERE ' + where, params).fetchone()[0]
                rows = db.execute('SELECT payload, id, status FROM planning_jobs WHERE ' + where + ' ORDER BY seq LIMIT ? OFFSET ?',
                                  params + (limit, offset)).fetchall()
                items = [self._decode(row, job_id=row[1], project_id=project_id,
                                      owner_id=owner_id, status=row[2]) for row in rows]
                db.execute('COMMIT')
            except BaseException:
                db.execute('ROLLBACK')
                raise
        return {'items': items, 'total': total,
                'limit': limit, 'offset': offset, 'durable': True,
                'generation_available': False}

    def cancel(self, job_id: str, project_id: str, owner_id: str) -> dict | None:
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                self._audit_owner_records(db, project_id, owner_id)
                row = db.execute('SELECT payload, status FROM planning_jobs WHERE id=? AND project_id=? AND owner_id=?',
                                 (job_id, project_id, owner_id)).fetchone()
                item = self._decode(row, job_id=job_id, project_id=project_id, owner_id=owner_id, status=row[1] if row else None)
                if item is not None and item['status'] == 'planned':
                    item['status'] = 'cancelled'
                    item['message'] = 'Plan cancelled before inference.'
                    item['cancelled_at'] = datetime.now(timezone.utc).isoformat()
                    db.execute('UPDATE planning_jobs SET status=?, payload=? WHERE id=?',
                               ('cancelled', json.dumps(item, allow_nan=False), job_id))
                db.execute('COMMIT')
            except BaseException:
                db.execute('ROLLBACK')
                raise
        return item
