"""Identity-scoped application preferences; small atomic patches, no UI-time fsync."""
import json
import os
import re

from fastapi import HTTPException, Request

from . import auth

KEY = re.compile(r'^[A-Za-z0-9_.:/-]{1,240}$')
MAX_BYTES = 65536


def identity(actor):
    native = os.getenv('MTA_NATIVE_SINGLE_USER', '').lower() in ('1', 'true', 'yes', 'on')
    if native:
        return 'native', None
    uid = int(actor['id'])
    return f'user:{uid}', uid if uid > 0 else None


def table(con):
    con.execute('CREATE TABLE IF NOT EXISTS application_preferences (owner TEXT PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, payload TEXT NOT NULL)')


def load(actor):
    owner, _ = identity(actor)
    with auth.db() as con:
        table(con)
        row = con.execute('SELECT payload FROM application_preferences WHERE owner=?', (owner,)).fetchone()
    return {'owner': owner, 'values': json.loads(row[0]) if row else {}}


def patch(actor, values):
    if not isinstance(values, dict) or len(values) > 128:
        raise ValueError('Expected up to 128 preference changes')
    for key, value in values.items():
        if not isinstance(key, str) or not KEY.fullmatch(key) or key in {'__proto__', 'constructor', 'prototype'}:
            raise ValueError('Invalid preference name')
        if value is not None and (not isinstance(value, str) or len(value.encode('utf-8')) > 32768):
            raise ValueError('Preference values must be strings up to 32 KiB')
    owner, uid = identity(actor)
    with auth.db() as con:
        if uid is None:con.execute('PRAGMA foreign_keys=OFF')  # local/dev identity has no users table or user row
        table(con)
        # A transaction serializes read/merge/write; unrelated tabs cannot lose
        # each other's keys by replacing an entire stale preference document.
        con.execute('BEGIN IMMEDIATE')
        row = con.execute('SELECT payload FROM application_preferences WHERE owner=?', (owner,)).fetchone()
        result = json.loads(row[0]) if row else {}
        for key, value in values.items():
            if value is None:
                result.pop(key, None)
            else:
                result[key] = value
        payload = json.dumps(result, ensure_ascii=True, allow_nan=False)
        if len(payload.encode()) > MAX_BYTES or len(result) > 1024:
            raise ValueError('Application preferences exceed 64 KiB / 1024 keys')
        con.execute('INSERT INTO application_preferences(owner,user_id,payload) VALUES(?,?,?) ON CONFLICT(owner) DO UPDATE SET payload=excluded.payload', (owner, uid, payload))
    return {'saved': True}


def bootstrap(request):
    actor = auth.session_user(request)
    result = load(actor) if actor else {'owner': None, 'values': {}}
    # Safe inside a script[type=application/json], including malicious strings.
    return json.dumps(result, ensure_ascii=True).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')


def register_routes(app):
    @app.get('/api/account/preferences')
    def get_preferences(request: Request):
        return load(auth.require_user(request))

    @app.patch('/api/account/preferences')
    async def update_preferences(request: Request):
        actor = auth.require_user(request)
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > MAX_BYTES:
                raise HTTPException(413, 'Preference patch exceeds 64 KiB')
        try:
            body = json.loads(data)
            if not isinstance(body, dict) or set(body) != {'values'}:
                raise ValueError('Expected a values object')
            from starlette.concurrency import run_in_threadpool
            return await run_in_threadpool(patch, actor, body['values'])
        except (ValueError, TypeError) as exc:
            raise HTTPException(422, str(exc)) from exc
