"""Behavioral recovery tests, including a child killed before publication."""
import asyncio
import json
import multiprocessing
import os
import signal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from app import main, ai_upload_transaction as ordinary, ai_recovered_stem_transaction as stems
from app import ai_async_track_transaction as async_tx


def project():
    return SimpleNamespace(tracks=[], clip_library=[], recovered_ai_imports=[])


@pytest.fixture
def media(tmp_path, monkeypatch):
    for name in ('audio', 'originals'):
        (tmp_path / name).mkdir()
    for tx in (ordinary, stems, async_tx):
        monkeypatch.setattr(tx, 'pdir', lambda pid: tmp_path)
        monkeypatch.setattr(tx, 'load_project', lambda pid: project())
    return tmp_path


@pytest.mark.parametrize('invalid', [None, ['../outside'], ['x', 'x'], [12], ['']])
def test_stem_entire_journal_preflight(media, invalid):
    stems.begin('p', 'receipt')
    (media / 'audio' / 'orphan.wav').write_bytes(b'keep until journal repaired')
    path = media / stems._NAME
    obj = json.loads(path.read_text()); obj['originals_before'] = invalid
    path.write_text(json.dumps(obj))
    with pytest.raises(RuntimeError):
        stems.reconcile('p')
    assert (media / 'audio' / 'orphan.wav').exists()
    assert path.exists()


@pytest.mark.parametrize('tx', [ordinary, stems, async_tx])
def test_recovery_rejects_symlink_before_any_cleanup(media, tx, tmp_path):
    if tx is ordinary:
        tx.begin('p'); args = ('p',); journal = media / tx.NAME
    elif tx is stems:
        tx.begin('p', 'receipt'); args = ('p',); journal = media / tx._NAME
    else:
        tx.begin('p', 'a' * 16, 'b' * 10 + '.wav'); args = ('p', 'a' * 16)
        journal = tx._receipt(*args)
    outside = tmp_path / 'outside'; outside.mkdir()
    (outside / 'secret.wav').write_bytes(b'private')
    (media / 'originals').rmdir(); (media / 'originals').symlink_to(outside, target_is_directory=True)
    (media / 'audio' / ('b' * 10 + '.wav')).write_bytes(b'orphan')
    with pytest.raises(RuntimeError):
        tx.reconcile(*args)
    assert (outside / 'secret.wav').read_bytes() == b'private'
    assert (media / 'audio' / ('b' * 10 + '.wav')).exists()
    assert journal.exists()


@pytest.mark.parametrize('state', ['unreferenced', 'committed', 'unreadable', 'replaced'])
def test_rollback_requires_identity_and_authoritative_state(monkeypatch, tmp_path, state):
    dst = tmp_path / 'audio.wav'; dst.write_bytes(b'ours')
    st = dst.stat(); identity = (st.st_dev, st.st_ino)
    persisted = project()
    if state == 'committed':
        persisted.clip_library.append(SimpleNamespace(filename=dst.name))
    if state == 'replaced':
        replacement = tmp_path / 'replacement'; replacement.write_bytes(b'other writer'); replacement.replace(dst)
    monkeypatch.setattr(main, 'load_project', Mock(side_effect=OSError('unreadable')) if state == 'unreadable' else lambda pid: persisted)
    main._rollback_unpublished_upload('p', dst, identity)
    assert dst.exists() == (state != 'unreferenced')
    if state == 'replaced':
        assert dst.read_bytes() == b'other writer'


def test_add_track_error_after_publication_preserves_media(monkeypatch, tmp_path):
    dst = tmp_path / 'new.wav'; dst.write_bytes(b'audio')
    editing = SimpleNamespace(sample_rate=44100, tracks=[], clip_library=[])
    persisted = project()
    monkeypatch.setattr(ordinary, 'begin', lambda pid: None)
    monkeypatch.setattr(main, '_project_for_actor', lambda *a: editing)
    monkeypatch.setattr(main, '_save_upload', lambda *a: (dst.name, dst, 100))
    monkeypatch.setattr(main, '_register_track_source_in_library', lambda *a: None)
    def publish_then_fail(value):
        persisted.tracks = list(value.tracks)
        raise OSError('directory fsync failed after replace')
    monkeypatch.setattr(main, 'save_project', publish_then_fail)
    monkeypatch.setattr(main, 'load_project', lambda pid: persisted)
    with pytest.raises(OSError):
        asyncio.run(main._add_track_under_project_lock('p', object(), SimpleNamespace(filename='input.wav')))
    assert dst.exists() and persisted.tracks[0].filename == dst.name


def test_async_invalid_sync_has_no_side_effects(monkeypatch):
    monkeypatch.setattr(main, '_project_for_actor', Mock(side_effect=AssertionError('must not read')))
    with pytest.raises(HTTPException) as error:
        asyncio.run(main.start_track_import_job('p', object(), SimpleNamespace(filename='a.wav'), sync_mode='bad'))
    assert error.value.status_code == 400


def test_async_thread_start_failure_finalizes_receipt(monkeypatch, media):
    from contextlib import nullcontext
    import app.ai_project_lock as locks
    import io
    monkeypatch.setattr(locks, 'project_publication_lock', lambda pid: nullcontext())
    monkeypatch.setattr(main, '_project_for_actor', lambda *a: SimpleNamespace(owner_user_id=1, tracks=[]))
    monkeypatch.setattr(main, '_ensure_workspace_capacity', lambda *a: None)
    monkeypatch.setattr(main, 'audio_path', lambda pid, name: media / 'audio' / name)
    monkeypatch.setattr(main, 'find_duplicate_project_file', lambda *a: None)
    monkeypatch.setattr(async_tx, 'preserve_job_original', lambda *a: None)
    monkeypatch.setattr(main.threading, 'Thread', Mock(return_value=SimpleNamespace(start=Mock(side_effect=RuntimeError('thread unavailable')))))
    request = SimpleNamespace(headers={})
    with pytest.raises(HTTPException) as error:
        asyncio.run(main.start_track_import_job('p', request, SimpleNamespace(filename='input.wav', file=io.BytesIO(b'audio'))))
    assert error.value.status_code == 503
    assert not list((media / 'audio').iterdir())
    assert not list(media.glob('.async-track-*.pending.json'))


@pytest.mark.parametrize('tx', [ordinary, stems, async_tx])
def test_fsync_failure_keeps_recovery_journal(media, tx, monkeypatch):
    if tx is ordinary:
        tx.begin('p'); args = ('p',); path = media / tx.NAME
    elif tx is stems:
        tx.begin('p', 'receipt'); args = ('p',); path = media / tx._NAME
    else:
        tx.begin('p', 'a' * 16, 'b' * 10 + '.wav'); args = ('p', 'a' * 16); path = tx._receipt(*args)
    monkeypatch.setattr(tx.os, 'fsync', Mock(side_effect=OSError('sync failure')))
    with pytest.raises(OSError): tx.reconcile(*args)
    assert path.exists()


def _interrupted_upload(root, ready):
    from pathlib import Path
    from app import ai_upload_transaction as tx
    tx.pdir = lambda pid: Path(root)
    tx.begin('p')
    (Path(root) / 'audio' / 'partial.wav').write_bytes(b'partial')
    ready.send(True)
    signal.pause()


@pytest.mark.skipif(os.name != 'posix', reason='SIGKILL recovery uses POSIX')
def test_real_process_kill_then_reconcile(media):
    ctx = multiprocessing.get_context('fork')
    receiver, sender = ctx.Pipe(duplex=False)
    child = ctx.Process(target=_interrupted_upload, args=(str(media), sender))
    child.start()
    try:
        assert receiver.poll(10) and receiver.recv()
        os.kill(child.pid, signal.SIGKILL); child.join(10)
        assert child.exitcode == -signal.SIGKILL
        assert ordinary.reconcile('p')['removed'] == 1
        assert not (media / 'audio' / 'partial.wav').exists()
    finally:
        if child.is_alive(): child.kill(); child.join(10)
        receiver.close(); sender.close()


@pytest.mark.parametrize('tx', [ordinary, stems, async_tx])
def test_durable_identity_preserves_replaced_files(media, tx):
    from app.ai_media_identity import record
    name = 'b' * 10 + '.wav'
    if tx is ordinary:
        tx.begin('p'); args = ('p',); journal = media / tx.NAME
    elif tx is stems:
        tx.begin('p', 'receipt'); args = ('p',); journal = media / tx._NAME
    else:
        tx.begin('p', 'a' * 16, name); args = ('p', 'a' * 16); journal = tx._receipt(*args)
    path = media / 'audio' / name; path.write_bytes(b'ours')
    record(journal, path)
    replacement = media / 'other'; replacement.write_bytes(b'concurrent writer'); replacement.replace(path)
    with pytest.raises(RuntimeError, match='replaced'):
        record(journal, path)
    assert tx.reconcile(*args)['removed'] == 0
    assert path.read_bytes() == b'concurrent writer'


@pytest.mark.parametrize('tx', [ordinary, stems, async_tx])
def test_invalid_identity_fails_closed(media, tx):
    name = 'b' * 10 + '.wav'
    if tx is ordinary:
        tx.begin('p'); args = ('p',); journal = media / tx.NAME
    elif tx is stems:
        tx.begin('p', 'receipt'); args = ('p',); journal = media / tx._NAME
    else:
        tx.begin('p', 'a' * 16, name); args = ('p', 'a' * 16); journal = tx._receipt(*args)
    path = media / 'audio' / name; path.write_bytes(b'keep')
    obj = json.loads(journal.read_text()); obj['identities'] = {'audio/../outside': [0, 1]}
    journal.write_text(json.dumps(obj))
    with pytest.raises(RuntimeError): tx.reconcile(*args)
    assert path.exists() and journal.exists()


def _configure_process(root, queue):
    from pathlib import Path
    from app import storage, ai_arranger_runtime
    storage.ROOT = Path(root)
    ai_arranger_runtime._ROOT = Path(queue)
    ordinary.pdir = storage.pdir
    ordinary.load_project = storage.load_project
    return storage


def _locked_writer(root, queue, pid, control):
    from app.ai_project_lock import project_publication_lock
    from app.ai_media_identity import record
    from app.models import Track
    storage = _configure_process(root, queue)
    with project_publication_lock(pid):
        ordinary.begin(pid)
        path = storage.audio_path(pid, 'committed.wav')
        path.write_bytes(b'audio')
        record(storage.pdir(pid) / ordinary.NAME, path)
        control.send('ready')
        control.recv()
        value = storage.load_project(pid)
        value.tracks.append(Track(id='track', name='Track', filename=path.name, duration_ms=100))
        storage.save_project(value)
    control.close()


def _locked_recovery(root, queue, pid, report):
    from app.ai_project_lock import project_publication_lock
    _configure_process(root, queue)
    report.send('attempting')
    with project_publication_lock(pid):
        report.send(ordinary.reconcile(pid))
    report.close()


@pytest.mark.skipif(os.name != 'posix', reason='Cross-process publication uses POSIX flock')
def test_real_process_recovery_waits_for_writer_commit(tmp_path, monkeypatch):
    from app import storage
    monkeypatch.setattr(storage, 'ROOT', tmp_path / 'projects')
    value = storage.create_project('Concurrent publication')
    queue = str(tmp_path / 'locks')
    ctx = multiprocessing.get_context('fork')
    control, writer_end = ctx.Pipe()
    report, recovery_end = ctx.Pipe(duplex=False)
    writer = ctx.Process(target=_locked_writer, args=(str(storage.ROOT), queue, value.id, writer_end))
    recovery = ctx.Process(target=_locked_recovery, args=(str(storage.ROOT), queue, value.id, recovery_end))
    writer.start()
    try:
        assert control.poll(10) and control.recv() == 'ready'
        recovery.start()
        assert report.poll(10) and report.recv() == 'attempting'
        assert not report.poll(0.2), 'recovery must wait for the writer lock'
        control.send('commit')
        assert report.poll(10)
        result = report.recv()
        writer.join(10); recovery.join(10)
        assert writer.exitcode == recovery.exitcode == 0
        assert result['committed'] and result['removed'] == 0
        assert storage.audio_path(value.id, 'committed.wav').exists()
        assert storage.load_project(value.id).tracks[0].filename == 'committed.wav'
    finally:
        for child in (writer, recovery):
            if child.is_alive(): child.kill(); child.join(10)
        control.close(); writer_end.close(); report.close(); recovery_end.close()
