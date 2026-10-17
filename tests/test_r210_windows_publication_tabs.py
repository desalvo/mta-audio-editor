"""Windows startup, OS locking, durable publication and Arranger readability."""
import errno
import io
import multiprocessing
import os
from pathlib import Path
import re
import time
import wave

import pytest
from app import platform_file_lock as locks


def _competing_lock(path, connection):
    fd = os.open(path, os.O_RDWR)
    try:
        try:
            locks.flock(fd, locks.LOCK_EX | locks.LOCK_NB)
        except BlockingIOError:
            connection.send(False)
        else:
            connection.send(True)
            locks.flock(fd, locks.LOCK_UN)
    finally:
        os.close(fd)
        connection.close()


def test_real_os_lock_excludes_another_process_and_releases(tmp_path):
    path = tmp_path / 'empty.lock'
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    context = multiprocessing.get_context('spawn')
    try:
        locks.flock(fd, locks.LOCK_EX)
        for expected in (False, True):
            if expected:
                locks.flock(fd, locks.LOCK_UN)
            receiver, sender = context.Pipe(duplex=False)
            child = context.Process(target=_competing_lock, args=(str(path), sender))
            child.start()
            try:
                assert receiver.poll(15)
                assert receiver.recv() is expected
                child.join(15)
                assert child.exitcode == 0
            finally:
                if child.is_alive():
                    child.kill()
                    child.join(10)
                receiver.close()
                sender.close()
    finally:
        os.close(fd)


def test_msvcrt_fixed_offset_contention_retry_and_unlock(tmp_path, monkeypatch):
    calls = []
    class Windows:
        LK_NBLCK = 2
        LK_UNLCK = 0
        @staticmethod
        def locking(fd, mode, count):
            calls.append((os.lseek(fd, 0, os.SEEK_CUR), mode, count))
            if len(calls) == 1:
                raise PermissionError(errno.EACCES, 'contended')
    monkeypatch.setattr(locks, '_posix', None)
    monkeypatch.setattr(locks, '_windows', Windows)
    monkeypatch.setattr(locks.time, 'sleep', lambda _: None)
    with (tmp_path / 'lock').open('w+b') as stream:
        stream.seek(12)
        locks.flock(stream.fileno(), locks.LOCK_EX)
        stream.seek(18)
        locks.flock(stream.fileno(), locks.LOCK_UN)
    assert calls == [(0, 2, 1), (0, 2, 1), (0, 0, 1)]


def test_absent_backend_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(locks, '_posix', None)
    monkeypatch.setattr(locks, '_windows', None)
    with (tmp_path / 'lock').open('w+b') as stream:
        with pytest.raises(RuntimeError, match='No supported'):
            locks.flock(stream.fileno(), locks.LOCK_EX)


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    from app import auth, storage, ai_arranger_runtime as queue, main
    deadline = time.monotonic() + 5
    while storage._GC_ACTIVE and time.monotonic() < deadline:
        time.sleep(.02)
    assert not storage._GC_ACTIVE
    monkeypatch.setattr(storage, 'ROOT', tmp_path / 'projects')
    monkeypatch.setattr(storage, 'SHARED_MEDIA_ROOT', tmp_path / 'shared')
    monkeypatch.setattr(storage, 'SHARED_AUDIO_ROOT', tmp_path / 'shared' / 'audio')
    monkeypatch.setattr(storage, 'SHARED_INDEX_PATH', tmp_path / 'shared' / 'index.json')
    monkeypatch.setattr(queue, '_ROOT', tmp_path / 'queue')
    monkeypatch.setattr(auth, 'DATA_ROOT', tmp_path / 'auth')
    monkeypatch.setattr(main, 'NATIVE_SINGLE_USER', True)
    monkeypatch.setenv('MTA_ALLOW_INSECURE_NO_AUTH', 'true')
    monkeypatch.setattr(main, '_start_background_services', lambda: None)
    monkeypatch.setattr(main, '_start_diagnostic_cleanup', lambda: None)
    return storage, queue, main


def test_native_lifespan_recovers_empty_outboxes_and_serves_health(isolated):
    from fastapi.testclient import TestClient
    with TestClient(isolated[2].app) as client:
        assert client.get('/api/health').status_code == 200


def test_generated_audio_publication_survives_reopen_and_replay(isolated, monkeypatch):
    from app import ai_publish_outbox as outbox
    storage, queue, main = isolated
    monkeypatch.delattr(os, 'fchmod', raising=False)
    project = storage.create_project('Recovered Windows audio')
    stream = io.BytesIO()
    with wave.open(stream, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(44100)
        wav.writeframes(b'\0' * 882)
    audio = stream.getvalue()
    outbox.stage('windows-recovery', project.id, audio,
                 {'wav': {'frames': 441, 'sample_rate': 44100, 'channels': 1},
                  'mode': 'arranger', 'input_source': 'master'})
    assert outbox.recover(main._publish_durable_generated_audio) == 1
    assert outbox.recover(main._publish_durable_generated_audio) == 0
    reopened = storage.load_project(project.id)
    assert len(reopened.tracks) == 1
    assert storage.audio_path(project.id, reopened.tracks[0].filename).read_bytes() == audio
    with outbox._open() as con:
        assert con.execute('SELECT state FROM publications').fetchone()[0] == 'published'


def test_project_lock_reentrant_and_released_after_error(isolated):
    from app.ai_project_lock import project_publication_lock
    with pytest.raises(ValueError, match='injected'):
        with project_publication_lock('project'):
            with project_publication_lock('project'):
                raise ValueError('injected')
    with project_publication_lock('project'):
        pass


def test_windows_queue_liveness_never_sends_a_signal(isolated, monkeypatch):
    queue = isolated[1]
    with queue._db() as con:
        con.execute("INSERT INTO jobs(job_id,project_id,operation,state,rank,created_at,runner_pid,phase,message) VALUES('old','project','test','running',1,1,1234,'running','test')")
    monkeypatch.setattr(queue.sys, 'platform', 'win32')
    monkeypatch.setattr(queue, '_process_identity', lambda pid: 'win32:123')
    monkeypatch.setattr(queue.os, 'kill', lambda *args: pytest.fail('Must never signal a Windows process'))
    assert queue.get('old')['state'] == 'running'
    monkeypatch.setattr(queue, '_process_identity', lambda pid: None)
    assert queue.get('old')['state'] == 'interrupted'


@pytest.mark.skipif(os.name != 'nt', reason='Requires real Win32 process APIs')
def test_windows_creation_identity_is_stable():
    from app.windows_process_identity import process_identity
    identity = process_identity(os.getpid())
    assert identity.startswith('win32:')
    assert process_identity(os.getpid()) == identity
    assert process_identity(2147483647) is None


def test_unselected_arranger_tabs_have_readable_text_and_focus():
    css = (Path(__file__).parents[1] / 'app/static/app.css').read_text(encoding='utf-8')
    def luminance(hexcolor):
        channels = [int(hexcolor[i:i+2], 16) / 255 for i in (0, 2, 4)]
        linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in channels]
        return sum(c * w for c, w in zip(linear, (.2126, .7152, .0722)))
    for selector in ('.ai-arranger .arranger-tabs button', '.ai-arranger .arranger-tabs [aria-selected=true]'):
        block = re.search(re.escape(selector) + r'\{([^}]+)\}', css).group(1)
        color = re.search(r'(?:^|;)color:#([a-f0-9]{6})!important', block).group(1)
        background = re.search(r'background:#([a-f0-9]{6})', block).group(1)
        values = sorted((luminance(color), luminance(background)))
        assert (values[1] + .05) / (values[0] + .05) >= 4.5
        assert '-webkit-text-fill-color:#' + color + '!important' in block
    assert '.ai-arranger .arranger-tabs button:focus-visible' in css


def test_native_private_settings_without_unix_fchmod(tmp_path, monkeypatch):
    from app import native_ai_account as account, native_ai_routing as routing
    monkeypatch.setenv('MTA_NATIVE_AI_ACCOUNT', str(tmp_path / 'account.json'))
    monkeypatch.setenv('MTA_NATIVE_AI_CONFIG', str(tmp_path / 'workers.json'))
    monkeypatch.delattr(os, 'fchmod', raising=False)
    account._write({'state': 'disconnected'})
    assert account.public_status()['state'] == 'disconnected'
    routing.configure('whisper', 'local')
    assert routing._read()['workers']['whisper']['mode'] == 'local'


def test_result_cache_without_unix_directory_flags(tmp_path, monkeypatch):
    from app import ai_result_cache as cache
    monkeypatch.setenv('MTA_AI_RESULT_CACHE_DIR', str(tmp_path / 'cache'))
    monkeypatch.delattr(os, 'O_DIRECTORY', raising=False)
    monkeypatch.delattr(os, 'O_NOFOLLOW', raising=False)
    payload = b'{"result":true}'
    assert cache.save(1, 'a' * 32, payload, 'application/json', 'job')
    assert cache.load(1, 'a' * 32, 'job') == (payload, 'application/json')
