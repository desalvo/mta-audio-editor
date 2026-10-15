import importlib.util
from pathlib import Path
from urllib.error import HTTPError

p = Path(__file__).parent / 'scripts/repositories/verify_public_pages.py'
spec = importlib.util.spec_from_file_location('verify_pages', p)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def prepare(tmp_path):
    for distro in ('el9', 'el10'):
        d = tmp_path / 'rpm/early' / distro / 'repodata'
        d.mkdir(parents=True)
        (d / 'repomd.xml').write_bytes(b'good-index')


def test_all_targets_match(tmp_path, monkeypatch):
    prepare(tmp_path)
    def fetch(url, token, timeout):
        return b'good-index' if url.endswith('repodata/repomd.xml') else b'nonempty'
    monkeypatch.setattr(m, 'fetch', fetch)
    assert m.verify(tmp_path, 'https://host/repo', 'early', '1', max_wait=0, interval=0)


def test_stale_index_fails_closed(tmp_path, monkeypatch):
    prepare(tmp_path)
    monkeypatch.setattr(m, 'fetch', lambda url, token, timeout: b'stale')
    assert not m.verify(tmp_path, 'https://host/repo', 'early', '1', max_wait=0, interval=0)


def test_unavailable_fails_closed(tmp_path, monkeypatch):
    prepare(tmp_path)
    def fail(url, token, timeout):
        raise HTTPError(url, 404, 'not deployed', {}, None)
    monkeypatch.setattr(m, 'fetch', fail)
    assert not m.verify(tmp_path, 'https://host/repo', 'early', '1', max_wait=0, interval=0)
