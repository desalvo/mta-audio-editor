"""Durable shared-project discussion, attachment expiry and revision contracts.

All project state stays on the server. The browser supplies neither ownership
nor recipient authority. Dashboard media never enters portable audio exports.
"""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import html
import json
import logging
import os
import re
import sqlite3
import subprocess
import threading
import time
import uuid

from fastapi import APIRouter, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from . import auth, storage
from .ai_project_lock import project_publication_lock

LOGGER = logging.getLogger(__name__)
router = APIRouter()
MAX_MEDIA_BYTES = 20 * 1024 * 1024
MAX_TEXT = 20000
MEDIA_ID = re.compile(r'^[0-9a-f]{32}$')
_STOP = threading.Event()
_THREAD = None


def _user(request):
    user = auth.require_user(request)
    if int(user['id']) <= 0:
        raise HTTPException(400, 'Collaboration requires a registered server account')
    return user


def _project(request, pid, *, shared=True):
    user = _user(request)
    try:
        project = storage.load_project(pid)
    except (OSError, ValueError):
        raise HTTPException(404, 'Project not found') from None
    uid = int(user['id'])
    from .account_lifecycle import is_deleted
    if is_deleted(uid) or is_deleted(project.owner_user_id):
        raise HTTPException(404, 'Project not found')
    if uid != project.owner_user_id and uid not in project.shared_with_user_ids:
        raise HTTPException(404, 'Project not found')
    if shared and not project.shared_with_user_ids:
        raise HTTPException(409, 'Project is no longer shared')
    return project, user


def _safe_path(pid, name):
    root = storage.pdir(pid)
    path = root / name
    if root.is_symlink() or path.is_symlink():
        raise ValueError('Unsafe collaboration path')
    return path


@contextmanager
def _db(pid):
    path = _safe_path(pid, 'collaboration.sqlite3')
    with sqlite3.connect(path, timeout=10) as con:
        os.chmod(path, 0o600)
        con.row_factory = sqlite3.Row
        con.executescript('''
          CREATE TABLE IF NOT EXISTS messages(
            id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,
            sender TEXT NOT NULL,text TEXT NOT NULL,created_at REAL NOT NULL,
            media_id TEXT,media_type TEXT,media_size INTEGER,expires_at REAL,
            expired INTEGER NOT NULL DEFAULT 0);
          CREATE TABLE IF NOT EXISTS receipts(user_id INTEGER PRIMARY KEY,last_read INTEGER NOT NULL);
          CREATE TABLE IF NOT EXISTS mail_outbox(
            message_id INTEGER NOT NULL,user_id INTEGER NOT NULL,state TEXT NOT NULL DEFAULT 'pending',
            attempts INTEGER NOT NULL DEFAULT 0,last_attempt REAL NOT NULL DEFAULT 0,
            PRIMARY KEY(message_id,user_id));
          CREATE TABLE IF NOT EXISTS revision_snapshots(revision INTEGER PRIMARY KEY,project_json TEXT NOT NULL);
        ''')
        yield con


def settings():
    path = auth.DATA_ROOT / 'collaboration-settings.json'
    if path.is_symlink():
        raise ValueError('Unsafe collaboration settings')
    value = json.loads(path.read_text()) if path.exists() else {}
    hours = value.get('attachment_ttl_hours', 24)
    if type(hours) not in (int, float) or not 1 <= hours <= 720:
        raise ValueError('Invalid collaboration attachment retention')
    return {'attachment_ttl_hours': hours, 'max_media_bytes': MAX_MEDIA_BYTES}


def validate_edit(current, incoming, actor):
    """Called inside the existing serialized project PUT before any mutation.

    Owners may resolve a stale collaborator snapshot. Collaborators must refresh
    rather than overwrite a newer revision. Existing AI-publication checks still
    run after this check and cannot be bypassed by owner priority.
    """
    if current.shared_with_user_ids and incoming.collaboration_revision != current.collaboration_revision:
        if int(actor['id']) != current.owner_user_id:
            raise HTTPException(409, 'PROJECT_COLLABORATION_CONFLICT')
        with _db(current.id) as con:
            base = con.execute('SELECT project_json FROM revision_snapshots WHERE revision=?', (incoming.collaboration_revision,)).fetchone()
        if base is None:
            # A very old owner snapshot is not a license to erase collaborators.
            raise HTTPException(409, 'PROJECT_COLLABORATION_CONFLICT')
        merged = merge_owner_snapshot(json.loads(base[0]), current.model_dump(mode='json'), incoming.model_dump(mode='json'))
        restored = type(incoming).model_validate(merged)
        for field in type(incoming).model_fields:
            setattr(incoming, field, getattr(restored, field))
    incoming.collaboration_revision = current.collaboration_revision


_MISSING = object()


def merge_owner_snapshot(base, server, owner):
    """Three-way merge; owner wins only paths changed by both participants.

    ID-bearing tracks/clips/events merge independently. Lists without durable
    IDs are atomic, because guessing positions after insertion would corrupt
    lyrics/timing. Concurrent edits to that same list are an owner conflict.
    """
    if owner == base:
        return deepcopy(server) if server is not _MISSING else _MISSING
    if server == base or server == owner:
        return deepcopy(owner) if owner is not _MISSING else _MISSING
    if all(isinstance(value, dict) for value in (base, server, owner)):
        result = {}
        for key in set(base) | set(server) | set(owner):
            value = merge_owner_snapshot(base.get(key, _MISSING), server.get(key, _MISSING), owner.get(key, _MISSING))
            if value is not _MISSING:
                result[key] = value
        return result
    if all(isinstance(value, list) for value in (base, server, owner)):
        if all(all(isinstance(item, dict) and isinstance(item.get('id'), str) for item in value) for value in (base, server, owner)):
            maps = [{item['id']: item for item in value} for value in (base, server, owner)]
            if all(len(value) == len(mapping) for value, mapping in zip((base, server, owner), maps)):
                result = {}
                for key in set(maps[0]) | set(maps[1]) | set(maps[2]):
                    value = merge_owner_snapshot(*(mapping.get(key, _MISSING) for mapping in maps))
                    if value is not _MISSING:
                        result[key] = value
                # Preserve server insertions, with owner ordering priority only
                # when the owner intentionally reordered the existing list.
                base_ids, server_ids, owner_ids = ([item['id'] for item in value] for value in (base, server, owner))
                order = owner_ids if owner_ids != base_ids else server_ids
                order = list(dict.fromkeys([*order, *server_ids, *owner_ids]))
                return [result[key] for key in order if key in result]
    return deepcopy(owner) if owner is not _MISSING else _MISSING


def before_persist(project, target):
    """Revision publication runs inside storage's cross-process project lock."""
    previous = json.loads(target.read_text()) if target.exists() else {}
    if previous.get('shared_with_user_ids') or project.shared_with_user_ids:
        if previous:
            with _db(project.id) as con:
                con.execute('INSERT OR IGNORE INTO revision_snapshots(revision,project_json) VALUES(?,?)', (int(previous.get('collaboration_revision', 0)), json.dumps(previous)))
                con.execute('DELETE FROM revision_snapshots WHERE revision NOT IN (SELECT revision FROM revision_snapshots ORDER BY revision DESC LIMIT 128)')
        project.collaboration_revision = int(previous.get('collaboration_revision', 0)) + 1
    else:
        project.collaboration_revision = max(int(previous.get('collaboration_revision', 0)), project.collaboration_revision)


def after_persist(project, previous_shared):
    if previous_shared and not project.shared_with_user_ids:
        end_sharing(project.id)


def end_sharing(pid):
    """The last revoke ends this discussion; no recoverable attachment trash."""
    directory = _safe_path(pid, 'collaboration-media')
    if directory.exists():
        for path in directory.iterdir():
            if path.is_symlink() or not path.is_file():
                raise ValueError('Unsafe collaboration media entry')
            path.unlink()
        directory.rmdir()
    for name in ('collaboration.sqlite3', 'collaboration.sqlite3-journal', 'collaboration.sqlite3-wal', 'collaboration.sqlite3-shm'):
        _safe_path(pid, name).unlink(missing_ok=True)


def cleanup(pid, *, now=None):
    now = time.time() if now is None else now
    if not _safe_path(pid, 'collaboration.sqlite3').exists():
        return 0
    removed = 0
    with _db(pid) as con:
        rows = con.execute('SELECT id,media_id FROM messages WHERE media_id IS NOT NULL AND expired=0 AND expires_at<=?', (now,)).fetchall()
        for row in rows:
            if not MEDIA_ID.fullmatch(row['media_id']):
                raise ValueError('Invalid stored media ID')
            _media_path(pid, row['media_id']).unlink(missing_ok=True)
            con.execute('UPDATE messages SET expired=1 WHERE id=?', (row['id'],))
            removed += 1
    return removed


def _media_path(pid, media_id):
    if not MEDIA_ID.fullmatch(media_id):
        raise HTTPException(404, 'Attachment not found')
    directory = _safe_path(pid, 'collaboration-media')
    path = directory / media_id
    if directory.is_symlink() or path.is_symlink():
        raise HTTPException(404, 'Attachment not found')
    return path


def _sender(user):
    return str(user['display_name'] or user['username']).replace('\r', ' ').replace('\n', ' ')[:200]


def _message(row, pid):
    data = dict(row)
    data['color'] = f'hsl({(int(row["user_id"]) * 137.507764) % 360:.3f} 66% 56%)'
    data['media_url'] = f'/api/projects/{pid}/collaboration/media/{row["media_id"]}' if row['media_id'] and not row['expired'] else None
    return data


def snapshot(project, uid, *, after=0):
    with _db(project.id) as con:
        rows = con.execute('SELECT * FROM messages WHERE id>? ORDER BY id LIMIT 200', (after,)).fetchall()
        last = con.execute('SELECT COALESCE(MAX(id),0) FROM messages').fetchone()[0]
        read = con.execute('SELECT last_read FROM receipts WHERE user_id=?', (uid,)).fetchone()
        unread = con.execute('SELECT COUNT(*) FROM messages WHERE id>? AND user_id!=?', (read[0] if read else 0, uid)).fetchone()[0]
    members = []
    for user_id in [project.owner_user_id, *project.shared_with_user_ids]:
        row = auth.get_user(user_id)
        if row:
            members.append({'id': user_id, 'name': _sender(row), 'owner': user_id == project.owner_user_id})
    return {'project_id': project.id, 'title': project.title, 'shared': bool(project.shared_with_user_ids),
            'owner_user_id': project.owner_user_id, 'revision': project.collaboration_revision,
            'messages': [_message(row, project.id) for row in rows], 'latest_message_id': last,
            'last_returned_id': rows[-1]['id'] if rows else after, 'has_more': bool(rows and rows[-1]['id'] < last),
            'unread': unread, 'participants': members, 'attachment_ttl_hours': settings()['attachment_ttl_hours']}


def _publish(project, user, text, *, media_id=None, media_type=None, media_size=0):
    if not isinstance(text, str) or len(text) > MAX_TEXT or (not text.strip() and not media_id):
        raise HTTPException(400, 'A message is required (maximum 20000 characters)')
    from .main import _ensure_workspace_capacity
    _ensure_workspace_capacity(project.owner_user_id, len(text.encode('utf-8')) + 4096)
    now = time.time()
    expires = now + settings()['attachment_ttl_hours'] * 3600 if media_id else None
    uid = int(user['id'])
    with _db(project.id) as con:
        cursor = con.execute('INSERT INTO messages(user_id,sender,text,created_at,media_id,media_type,media_size,expires_at) VALUES(?,?,?,?,?,?,?,?)',
                             (uid, _sender(user), text.strip(), now, media_id, media_type, media_size, expires))
        message_id = cursor.lastrowid
        for recipient in {project.owner_user_id, *project.shared_with_user_ids} - {uid}:
            con.execute('INSERT INTO mail_outbox(message_id,user_id) VALUES(?,?)', (message_id, recipient))
        row = con.execute('SELECT * FROM messages WHERE id=?', (message_id,)).fetchone()
    return _message(row, project.id)


def deliver_mail(pid, *, now=None):
    """Persistent best-effort outbox; membership is checked again before send."""
    now = time.time() if now is None else now
    cfg = auth.get_smtp_config()
    if not cfg.get('host') or not cfg.get('from_email'):
        return {'sent': 0, 'failed': 0, 'smtp_configured': False}
    sent = failed = 0
    with _db(pid) as con:
        rows = con.execute("SELECT o.*,m.sender,m.text,m.media_type FROM mail_outbox o JOIN messages m ON m.id=o.message_id WHERE (o.state='pending' AND o.last_attempt<?) OR (o.state='sending' AND o.last_attempt<?) ORDER BY o.message_id LIMIT 50", (now - 60, now - 600)).fetchall()
    for row in rows:
        with project_publication_lock(pid):
            project = storage.load_project(pid)
            if not project.shared_with_user_ids or not _safe_path(pid, 'collaboration.sqlite3').exists():
                break
            from .account_lifecycle import is_deleted
            if is_deleted(project.owner_user_id):
                with _db(pid) as con:
                    con.execute("UPDATE mail_outbox SET state='cancelled' WHERE state IN ('pending','sending')")
                break
            user = auth.get_user(row['user_id'])
            members = {project.owner_user_id, *project.shared_with_user_ids}
            if row['user_id'] not in members or not user or not user['active'] or not user['email_confirmed'] or is_deleted(row['user_id']):
                with _db(pid) as con:
                    con.execute("UPDATE mail_outbox SET state='cancelled' WHERE message_id=? AND user_id=?", (row['message_id'], row['user_id']))
                continue
            with _db(pid) as con:
                claimed = con.execute("UPDATE mail_outbox SET state='sending',attempts=attempts+1,last_attempt=? WHERE message_id=? AND user_id=? AND ((state='pending' AND last_attempt<?) OR (state='sending' AND last_attempt<?))", (now, row['message_id'], row['user_id'], now - 60, now - 600)).rowcount
                if not claimed:
                    continue
        # SMTP does not hold the editor's publication lock. The durable claim
        # prevents two server processes from sending this row concurrently.
        subject = f'MTA · {project.title} · {row["sender"]}'.replace('\r', ' ').replace('\n', ' ')
        body = f'Progetto / Project: {project.title}\nMittente / Sender: {row["sender"]}\n\n{row["text"]}'
        if row['media_type']:
            body += '\n[Immagine o audio nella dashboard condivisa / Image or audio in the shared dashboard]'
        try:
            auth.send_mail([user['email']], subject, body, '<p>' + html.escape(body).replace('\n', '<br>') + '</p>',
                           message_id='<mta-collaboration-' + hashlib.sha256(f'{pid}:{row["message_id"]}:{row["user_id"]}'.encode()).hexdigest() + '@mta.local>')
        except Exception:
            LOGGER.exception('Collaboration email delivery failed')
            failed += 1
            with project_publication_lock(pid):
                if _safe_path(pid, 'collaboration.sqlite3').exists():
                    with _db(pid) as con:
                        con.execute("UPDATE mail_outbox SET state='pending' WHERE message_id=? AND user_id=? AND last_attempt=?", (row['message_id'], row['user_id'], now))
        else:
            sent += 1
            with project_publication_lock(pid):
                if _safe_path(pid, 'collaboration.sqlite3').exists():
                    with _db(pid) as con:
                        con.execute("UPDATE mail_outbox SET state='sent' WHERE message_id=? AND user_id=? AND last_attempt=?", (row['message_id'], row['user_id'], now))
    return {'sent': sent, 'failed': failed, 'smtp_configured': True}


@router.get('/api/projects/{pid}/collaboration')
def get_dashboard(pid: str, request: Request, after: int = 0):
    with project_publication_lock(pid):
        project, user = _project(request, pid, shared=False)
        if not project.shared_with_user_ids:
            return {'shared': False, 'project_id': pid, 'revision': project.collaboration_revision, 'unread': 0}
        cleanup(pid)
        return snapshot(project, int(user['id']), after=max(0, after))


@router.post('/api/projects/{pid}/collaboration/messages')
def send_message(pid: str, request: Request, body: dict):
    if set(body) != {'text'}:
        raise HTTPException(400, 'Only message text is accepted')
    with project_publication_lock(pid):
        project, user = _project(request, pid)
        return _publish(project, user, body['text'])


@router.post('/api/projects/{pid}/collaboration/read')
def mark_read(pid: str, request: Request, body: dict):
    if set(body) != {'message_id'} or type(body['message_id']) is not int or body['message_id'] < 0:
        raise HTTPException(400, 'Invalid read cursor')
    with project_publication_lock(pid):
        project, user = _project(request, pid)
        with _db(pid) as con:
            last = con.execute('SELECT COALESCE(MAX(id),0) FROM messages').fetchone()[0]
            read = min(last, body['message_id'])
            con.execute('INSERT INTO receipts(user_id,last_read) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET last_read=MAX(last_read,excluded.last_read)', (int(user['id']), read))
        return {'ok': True, 'last_read': read}


@router.post('/api/projects/{pid}/collaboration/leave')
def leave(pid: str, request: Request):
    with project_publication_lock(pid):
        project, user = _project(request, pid)
        uid = int(user['id'])
        if uid == project.owner_user_id:
            raise HTTPException(400, 'The owner manages sharing from the share window')
        project.shared_with_user_ids = [value for value in project.shared_with_user_ids if value != uid]
        storage.save_project(project)
        return {'ok': True}


@router.post('/api/projects/{pid}/collaboration/media')
def upload_media(pid: str, request: Request, file: UploadFile):
    with project_publication_lock(pid):
        project, user = _project(request, pid)
        media_id = uuid.uuid4().hex
        path = _media_path(pid, media_id)
        path.parent.mkdir(exist_ok=True, mode=0o700)
        total = 0
        try:
            with path.open('xb') as handle:
                from .platform_file_lock import private_mode
                private_mode(handle.fileno())
                while chunk := file.file.read(1024 * 1024):
                    total += len(chunk)
                    if total > MAX_MEDIA_BYTES:
                        raise HTTPException(413, 'Dashboard attachment exceeds 20 MiB')
                    from .main import _ensure_workspace_capacity
                    _ensure_workspace_capacity(project.owner_user_id, len(chunk))
                    handle.write(chunk)
                handle.flush()
                os.fsync(handle.fileno())
            mime = _validate_media(path)
            return _publish(project, user, '', media_id=media_id, media_type=mime, media_size=total)
        except Exception:
            path.unlink(missing_ok=True)
            raise


def _validate_media(path):
    head = path.read_bytes()[:32]
    if head.startswith((b'\x89PNG\r\n\x1a\n', b'\xff\xd8\xff', b'GIF87a', b'GIF89a')) or (head.startswith(b'RIFF') and head[8:12] == b'WEBP'):
        from PIL import Image
        try:
            with Image.open(path) as image:
                if image.width * image.height > 25_000_000:
                    raise ValueError('Image exceeds 25 megapixels')
                mime = Image.MIME[image.format]
                image.verify()
            return mime
        except Exception as exc:
            raise HTTPException(400, 'Invalid dashboard image') from exc
    audio_magic = ((head.startswith(b'RIFF') and head[8:12] == b'WAVE') or
                   head.startswith((b'ID3', b'OggS', b'fLaC', b'\x1aE\xdf\xa3')) or
                   (len(head) > 2 and head[0] == 255 and head[1] & 224 == 224) or head[4:8] == b'ftyp')
    if not audio_magic:
        raise HTTPException(400, 'Unsupported dashboard media signature')
    try:
        # No playlists or remote protocol fetching from an uploaded container.
        result = subprocess.run(['ffprobe', '-v', 'error', '-protocol_whitelist', 'file,pipe',
                                 '-probesize', '8388608', '-analyzeduration', '5000000',
                                 '-show_streams', '-show_format', '-of', 'json', str(path)],
                                capture_output=True, text=True, timeout=15, check=True)
        info = json.loads(result.stdout)
        streams = info.get('streams', [])
        if not streams or any(stream.get('codec_type') != 'audio' for stream in streams):
            raise ValueError('Only audio streams are accepted')
        duration = float(info.get('format', {}).get('duration', 0))
        if not 0 < duration <= 1800:
            raise ValueError('Audio must be between zero and 30 minutes')
        format_name = info.get('format', {}).get('format_name', '')
        choices = [('wav', 'audio/wav'), ('mp3', 'audio/mpeg'), ('ogg', 'audio/ogg'), ('webm', 'audio/webm'), ('matroska', 'audio/webm'), ('flac', 'audio/flac'), ('mp4', 'audio/mp4')]
        mime = next((mime for kind, mime in choices if kind in format_name), None)
        if not mime:
            raise ValueError('Unsupported audio container')
        return mime
    except Exception as exc:
        raise HTTPException(400, 'Invalid or unsupported dashboard audio') from exc


@router.get('/api/projects/{pid}/collaboration/media/{media_id}')
def get_media(pid: str, media_id: str, request: Request):
    with project_publication_lock(pid):
        _project(request, pid)
        cleanup(pid)
        with _db(pid) as con:
            row = con.execute('SELECT * FROM messages WHERE media_id=? AND expired=0', (media_id,)).fetchone()
        path = _media_path(pid, media_id)
        if not row or not path.is_file():
            raise HTTPException(404, 'Attachment expired or unavailable')
        return FileResponse(path, media_type=row['media_type'], headers={'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff'})


@router.get('/api/projects/{pid}/collaboration/events')
async def events(pid: str, request: Request):
    _project(request, pid)

    async def stream():
        previous = None
        # A bounded stream lets the common admission/drain barrier quiesce
        # connected clients; EventSource reconnects using a fresh admission.
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline and not await request.is_disconnected():
            try:
                with project_publication_lock(pid):
                    project, user = _project(request, pid)
                    cleanup(pid)
                    status = snapshot(project, int(user['id']))
                    # Changes are applied by a guarded browser callback, never
                    # blindly replacing dirty local state.
                    status['project'] = project.model_dump(mode='json')
                encoded = json.dumps(status, ensure_ascii=False, separators=(',', ':'))
                if encoded != previous:
                    yield 'retry: 500\nevent: collaboration\ndata: ' + encoded + '\n\n'
                    previous = encoded
                else:
                    yield ': keepalive\n\n'
            except HTTPException:
                yield 'event: revoked\ndata: {}\n\n'
                return
            await asyncio.sleep(0.5)
    return StreamingResponse(stream(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache, no-store', 'X-Accel-Buffering': 'no'})


@router.get('/api/admin/collaboration')
def admin_get(request: Request):
    auth.require_admin(request)
    return settings()


@router.put('/api/admin/collaboration')
def admin_save(request: Request, body: dict):
    auth.require_admin(request)
    hours = body.get('attachment_ttl_hours')
    if set(body) != {'attachment_ttl_hours'} or type(hours) not in (int, float) or not 1 <= hours <= 720:
        raise HTTPException(400, 'Attachment retention must be 1–720 hours')
    auth.DATA_ROOT.mkdir(parents=True, exist_ok=True)
    target = auth.DATA_ROOT / 'collaboration-settings.json'
    if target.is_symlink():
        raise HTTPException(400, 'Unsafe settings path')
    temporary = target.with_name('collaboration-settings-' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_text(json.dumps({'attachment_ttl_hours': hours}) + '\n')
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return settings()


def maintenance_once():
    result = {'attachments_removed': 0, 'emails_sent': 0, 'projects_failed': 0}
    for directory in storage.ROOT.iterdir():
        if not directory.is_dir() or not storage.PID_RE.fullmatch(directory.name) or directory.is_symlink():
            continue
        pid = directory.name
        if not (directory / 'collaboration.sqlite3').exists():
            continue
        try:
            with project_publication_lock(pid):
                project = storage.load_project(pid)
                if not project.shared_with_user_ids:
                    end_sharing(pid)
                    continue
                result['attachments_removed'] += cleanup(pid)
            result['emails_sent'] += deliver_mail(pid)['sent']
        except Exception:
            LOGGER.exception('Project collaboration maintenance failed for %s', pid)
            result['projects_failed'] += 1
    return result


def start_maintenance():
    global _THREAD
    if _THREAD is not None and _THREAD.is_alive():
        return
    _STOP.clear()

    def run():
        while not _STOP.wait(30):
            from .service_admission import periodic
            try:
                periodic('project-collaboration-maintenance', maintenance_once)
            except (OSError, ValueError, sqlite3.Error):
                LOGGER.exception('Collaboration maintenance unavailable; durable work retained for retry')
    _THREAD = threading.Thread(target=run, name='mta-collaboration-maintenance', daemon=True)
    _THREAD.start()


def stop_maintenance():
    _STOP.set()
