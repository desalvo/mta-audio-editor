"""Actual SQLite writer contention + authenticated FFmpeg export/poll/download."""
import json
import sqlite3
import subprocess
import threading
import time
import wave

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from app import auth, storage, account_lifecycle, regime_service_lease


@pytest.fixture
def installed(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, 'DATA_ROOT', tmp_path / 'data')
    monkeypatch.setattr(storage, 'ROOT', tmp_path / 'projects')
    monkeypatch.setenv('MTA_ADMIN_PASSWORD', 'administrator-password')
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH', raising=False)
    monkeypatch.delenv('MTA_NATIVE_SINGLE_USER', raising=False)
    auth.init_auth_db()
    with auth.db() as con:
        account_lifecycle.init(con)
        con.execute('''INSERT INTO users(username,email,password_hash,role,active,email_confirmed,created_at,updated_at)
            VALUES('export-user','export@example.test','unused','user',1,1,1,1)''')
        uid = con.execute("SELECT id FROM users WHERE username='export-user'").fetchone()[0]
    # A short real SQLite timeout makes a regression fail promptly; no fake DB,
    # authentication or render result is used.
    original = regime_service_lease.connect
    def short_timeout(*args, **kwargs):
        kwargs['timeout'] = .1
        return original(*args, **kwargs)
    monkeypatch.setattr(regime_service_lease, 'connect', short_timeout)
    return uid


def request_for(uid):
    request = Request({'type': 'http', 'headers': [(b'user-agent', b'testclient')]})
    token = auth.create_session(uid, request)
    return Request({'type': 'http', 'method': 'GET', 'path': '/',
                    'headers': [(b'cookie', ('mta_session=' + token).encode())]})


def test_ready_auth_and_owner_checks_remain_read_only_with_another_writer(installed):
    request = request_for(installed)
    with sqlite3.connect(auth.db_path(), timeout=.1) as writer:
        writer.execute('BEGIN IMMEDIATE')
        writer.execute("UPDATE smtp_config SET from_name='uncommitted writer' WHERE id=1")
        # This is the same harmless-looking write which the old initializer
        # attempted on every poll. It really conflicts with the reserved writer.
        with auth.db() as con, pytest.raises(sqlite3.OperationalError, match='locked'):
            con.execute('INSERT OR IGNORE INTO smtp_config(id) VALUES(1)')
        for _ in range(4):
            assert auth.session_user(request)['id'] == installed
            assert account_lifecycle.info(installed)['state'] == 'legacy'
        writer.rollback()


@pytest.mark.parametrize('fmt', ['mp3', 'wav', 'flac'])
@pytest.mark.parametrize('kind', ['project', 'track'])
def test_real_export_poll_and_download_work_while_sqlite_writer_is_held(installed, monkeypatch, fmt, kind):
    from app import main
    from app.models import Track
    monkeypatch.setattr(main, 'NATIVE_SINGLE_USER', False)
    project = storage.create_project('Concurrent export', owner_user_id=installed)
    path = storage.audio_path(project.id, 'tone.wav')
    with wave.open(str(path), 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(44100)
        audio.writeframes(b'\0\0' * 11025)
    project.tracks = [Track(id='track', name='Tone', filename='tone.wav', duration_ms=250,
                            sample_rate=44100, channels=1)]
    storage.save_project(project)
    request = request_for(installed)
    client = TestClient(main.app)
    client.cookies.set('mta_session', request.cookies['mta_session'])
    client.headers['accept-language'] = 'it'
    url = (f'/api/projects/{project.id}/configured-export-jobs' if kind == 'project' else
           f'/api/projects/{project.id}/tracks/track/track-export-jobs')
    with sqlite3.connect(auth.db_path(), timeout=.1) as writer:
        writer.execute('BEGIN IMMEDIATE')
        writer.execute("UPDATE smtp_config SET from_name='writer held during real FFmpeg' WHERE id=1")
        response = client.post(url, headers={'X-MTA-Request': '1'}, json={'format': fmt})
        assert response.status_code == 200, response.text
        job = response.json()['id']
        deadline = time.monotonic() + 20
        polls = 0
        while time.monotonic() < deadline:
            response = client.get('/api/media-jobs/' + job)
            assert response.status_code == 200, response.text
            polls += 1
            state = response.json()
            if state['status'] in {'completed', 'failed'}:
                break
            threading.Event().wait(.03)
        assert state['status'] == 'completed', state
        assert polls >= 1
        download = client.get(state['result']['download_url'])
        assert download.status_code == 200 and len(download.content) > 100, download.text[:200]
        assert download.headers['content-type'].startswith({'mp3': 'audio/mpeg', 'wav': 'audio/wav', 'flac': 'audio/flac'}[fmt])
        downloaded = auth.data_root() / ('verified-download-' + kind + '.' + fmt)
        downloaded.write_bytes(download.content)
        probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_name',
                                '-of', 'json', str(downloaded)], check=True, capture_output=True, text=True, timeout=10)
        codec = json.loads(probe.stdout)['streams'][0]['codec_name']
        assert codec.startswith('pcm_') if fmt == 'wav' else codec == fmt
        writer.rollback()
    with auth.db() as con:
        assert con.execute('SELECT browser_language FROM users WHERE id=?', (installed,)).fetchone()[0] == 'en'
    client.cookies.clear()
    assert client.get('/api/media-jobs/' + job).status_code == 401


@pytest.mark.parametrize('missing', ['language', 'smtp-row', 'index'])
def test_real_missing_schema_or_defaults_still_migrate(installed, missing):
    with auth.db() as con:
        if missing == 'language':
            con.execute('ALTER TABLE users DROP COLUMN language')
        elif missing == 'smtp-row':
            con.execute('DELETE FROM smtp_config')
        else:
            con.execute('DROP INDEX idx_model_access_tokens_user')
    auth.init_auth_db()
    with auth.db() as con:
        assert auth._auth_schema_ready(con)
        assert con.execute('SELECT id FROM users WHERE id=?', (installed,)).fetchone()[0] == installed


def test_database_replacement_is_not_hidden_by_a_process_cache(installed, tmp_path, monkeypatch):
    monkeypatch.setattr(auth, 'DATA_ROOT', tmp_path / 'second-installation')
    auth.init_auth_db()
    assert auth.find_user('admin')['role'] == 'admin'
    assert auth.find_user('export-user') is None
