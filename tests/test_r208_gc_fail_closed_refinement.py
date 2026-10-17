"""Storage safety regressions for existing r208 GC recovery."""
import json
import threading

import pytest
from app import storage


@pytest.fixture(autouse=True)
def finish_prior_gc_workers():
    # Other suites schedule daemon GC. Finish them before globally replacing
    # pdir/load_project, otherwise an unrelated worker consumes this test journal.
    for worker in threading.enumerate():
        if worker.name.startswith('mta-gc-'):
            worker.join(5)
            assert not worker.is_alive()


def test_rejects_corrupt_gc_queue_without_discarding_it(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'pdir', lambda pid: tmp_path)
    queue = tmp_path / storage.GC_QUEUE_NAME
    queue.write_text('{broken')
    with pytest.raises(ValueError):
        storage._read_gc_queue('test')
    assert queue.read_text() == '{broken'


@pytest.mark.parametrize('payload', [[], {'version': 2, 'audio': []},
                                     {'version': 1, 'audio': ['x.wav', 'x.wav']},
                                     {'version': 1, 'audio': ['../escape']}])
def test_rejects_invalid_gc_queue(tmp_path, monkeypatch, payload):
    monkeypatch.setattr(storage, 'pdir', lambda pid: tmp_path)
    (tmp_path / storage.GC_QUEUE_NAME).write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        storage._read_gc_queue('test')


def test_rejects_gc_queue_symlink(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'pdir', lambda pid: tmp_path)
    outside = tmp_path / 'other'
    outside.write_text('{"version":1,"audio":[]}')
    (tmp_path / storage.GC_QUEUE_NAME).symlink_to(outside)
    with pytest.raises(ValueError):
        storage._read_gc_queue('test')


def test_gc_does_not_unlink_symlink_or_touch_target(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'pdir', lambda pid: tmp_path)
    monkeypatch.setattr(storage, 'load_project', lambda pid: type('P', (), {'tracks': [], 'clip_library': []})())
    (tmp_path / 'audio').mkdir()
    outside = tmp_path / 'outside.wav'
    outside.write_bytes(b'preserve')
    (tmp_path / 'audio' / 'orphan.wav').symlink_to(outside)
    storage._write_gc_queue('test', {'orphan.wav'})
    report = storage.run_project_gc('test')
    assert report['deleted'] == 0
    assert report['skipped'] == 1
    assert (tmp_path / 'audio' / 'orphan.wav').is_symlink()
    assert outside.read_bytes() == b'preserve'


def test_gc_rejects_symlink_audio_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'pdir', lambda pid: tmp_path)
    monkeypatch.setattr(storage, 'load_project', lambda pid: type('P', (), {'tracks': [], 'clip_library': []})())
    external = tmp_path / 'other'
    external.mkdir()
    (external / 'orphan.wav').write_bytes(b'preserve')
    (tmp_path / 'audio').symlink_to(external, target_is_directory=True)
    storage._write_gc_queue('test', {'orphan.wav'})
    assert storage.run_project_gc('test')['deleted'] == 0
    with pytest.raises(ValueError):
        storage.reconcile_project_gc('test')
    assert (external / 'orphan.wav').read_bytes() == b'preserve'

@pytest.mark.parametrize('names', [set(), {'orphan.wav'}])
def test_gc_writer_rejects_symlink_journal(tmp_path, monkeypatch, names):
    monkeypatch.setattr(storage, 'pdir', lambda pid: tmp_path)
    outside = tmp_path / 'outside.json'
    outside.write_text('external content')
    (tmp_path / storage.GC_QUEUE_NAME).symlink_to(outside)
    with pytest.raises(ValueError):
        storage._write_gc_queue('test', names)
    assert outside.read_text() == 'external content'
