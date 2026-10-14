import threading
import pytest
from app import ai_publish_outbox as outbox
from app import ai_arranger_runtime as runtime

@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, '_ROOT', tmp_path / 'jobs')

def test_publish_and_replay(isolated):
    outbox.stage('job1', 'proj', b'audio', {'mode': 'arranger'})
    seen = []
    assert outbox.recover(lambda *a: seen.append(a)) == 1
    assert outbox.recover(lambda *a: seen.append(a)) == 0
    assert len(seen) == 1
    assert outbox.status('job1')['state'] == 'published'

def test_crash_after_callback_recovery(isolated):
    outbox.stage('job2', 'proj', b'audio', {'mode': 'remix'})
    seen = set()
    def callback(jid, *_):
        first = jid not in seen
        seen.add(jid)
        if first: raise RuntimeError('injected crash')
    with pytest.raises(RuntimeError): outbox.recover(callback)
    assert outbox.recover(callback) == 1
    assert seen == {'job2'}

def test_conflicting_stage(isolated):
    outbox.stage('job3', 'proj', b'audio', {'mode':'remix'})
    outbox.stage('job3', 'proj', b'audio', {'mode':'remix'})
    with pytest.raises(ValueError): outbox.stage('job3', 'proj', b'other', {'mode':'remix'})

def test_tampered_audio(isolated):
    outbox.stage('job4', 'proj', b'audio', {'mode':'remix'})
    outbox._stage_path('job4').write_bytes(b'tampered')
    with pytest.raises(ValueError, match='checksum'): outbox.recover(lambda *args: None)

def test_competing_consumers(isolated):
    outbox.stage('job5', 'proj', b'audio', {'mode':'remix'})
    published, results = [], []
    def worker(): results.append(outbox.recover(lambda jid, *_: published.append(jid)))
    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert sum(results) == 1
    assert published == ['job5']
