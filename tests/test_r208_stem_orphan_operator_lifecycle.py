import json
from types import SimpleNamespace
import pytest
from app import ai_recovered_stem_transaction as tx


def setup(monkeypatch, tmp_path):
    folder = tmp_path / 'proj'
    (folder / 'audio').mkdir(parents=True)
    (folder / 'originals').mkdir()
    monkeypatch.setattr(tx, 'pdir', lambda _: folder)
    monkeypatch.setattr(tx, 'load_project', lambda _: SimpleNamespace(recovered_ai_imports=[], tracks=[], clip_library=[]))
    tx.begin('p', 'receipt')
    (folder / 'audio' / 'orphan.wav').write_bytes(b'untouched')
    tx.reconcile('p')
    return folder


def test_review_quarantine_and_restart(monkeypatch, tmp_path):
    folder = setup(monkeypatch, tmp_path)
    assert tx.review_preserved('p')['items'][0]['present']
    result = tx.quarantine_preserved('p', 'receipt', 'audio/orphan.wav')
    assert result['quarantined']
    assert not (folder / 'audio' / 'orphan.wav').exists()
    assert (folder / '.recovered-stems-quarantine' / result['quarantine_name']).read_bytes() == b'untouched'
    assert not tx.review_preserved('p')['items'][0]['present']
    assert json.loads((folder / tx._ORPHANS).read_text())['items'][0]['receipt'] == 'receipt'
    with pytest.raises(RuntimeError):
        tx.quarantine_preserved('p', 'receipt', 'audio/orphan.wav')


def test_unreviewed_and_referenced_files_fail_closed(monkeypatch, tmp_path):
    folder = setup(monkeypatch, tmp_path)
    (folder / 'audio' / 'other.wav').write_bytes(b'private')
    with pytest.raises(RuntimeError):
        tx.quarantine_preserved('p', 'receipt', 'audio/other.wav')
    monkeypatch.setattr(tx, 'load_project', lambda _: SimpleNamespace(tracks=[SimpleNamespace(filename='orphan.wav')], clip_library=[]))
    with pytest.raises(RuntimeError, match='referenced'):
        tx.quarantine_preserved('p', 'receipt', 'audio/orphan.wav')
    assert (folder / 'audio' / 'orphan.wav').read_bytes() == b'untouched'


def test_pending_journal_and_unsafe_report_rejected(monkeypatch, tmp_path):
    folder = setup(monkeypatch, tmp_path)
    tx.begin('p', 'next')
    with pytest.raises(RuntimeError, match='Pending'):
        tx.quarantine_preserved('p', 'receipt', 'audio/orphan.wav')
    (folder / tx._NAME).unlink()
    (folder / tx._ORPHANS).unlink()
    (folder / tx._ORPHANS).symlink_to(folder / 'audio' / 'orphan.wav')
    with pytest.raises(RuntimeError, match='Unsafe'):
        tx.review_preserved('p')
