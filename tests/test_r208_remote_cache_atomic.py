"""Result replay must remain private, immutable and safe under concurrent writes."""
from concurrent.futures import ThreadPoolExecutor
import os

from app import ai_result_cache as cache


def _setup(monkeypatch, tmp_path):
    monkeypatch.setenv('MTA_AI_RESULT_CACHE_DIR', str(tmp_path))
    monkeypatch.setenv('MTA_AI_RESULT_CACHE_CLEANUP_INTERVAL', '86400')


def test_cache_rejects_symlinked_payload(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    cache.save(1, 'key-for-cache-12345', b'first', 'audio/wav', 'job1')
    blob, _ = cache._paths(tmp_path, 1, 'key-for-cache-12345')
    target = tmp_path / 'outside'
    target.write_bytes(b'first')
    blob.unlink()
    blob.symlink_to(target)
    assert cache.load(1, 'key-for-cache-12345', 'job1') is None


def test_cache_rejects_hardlinked_payload(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    cache.save(1, 'key-for-cache-12345', b'first', 'audio/wav', 'job1')
    blob, _ = cache._paths(tmp_path, 1, 'key-for-cache-12345')
    os.link(blob, tmp_path / 'alias')
    assert cache.load(1, 'key-for-cache-12345', 'job1') is None


def test_cache_rejects_corrupt_metadata(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    cache.save(1, 'key-for-cache-12345', b'first', 'audio/wav', 'job1')
    _, metadata = cache._paths(tmp_path, 1, 'key-for-cache-12345')
    metadata.write_text('{')
    assert cache.load(1, 'key-for-cache-12345', 'job1') is None


def test_cache_concurrent_saves_do_not_mix_artifacts(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)
    def writer(i):
        for _ in range(10):
            cache.save(1, 'key-for-cache-12345', (str(i)*1000).encode(), 'audio/wav', 'job1')
            result = cache.load(1, 'key-for-cache-12345', 'job1')
            assert result is not None
            assert result[0] in (b'1'*1000, b'2'*1000, b'3'*1000)
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(writer, (1,2,3)))
