import pytest
from test_r208_stem_orphan_operator_lifecycle import setup
from app import ai_recovered_stem_transaction as tx


def test_quarantine_inventory_survives_restart_and_restores(monkeypatch, tmp_path):
    folder = setup(monkeypatch, tmp_path)
    result = tx.quarantine_preserved('p', 'receipt', 'audio/orphan.wav')
    inv = tx.review_quarantine('p')
    assert inv['items'][0]['present']
    assert inv['items'][0]['quarantine_name'] == result['quarantine_name']
    assert tx.restore_quarantined('p', result['quarantine_name'])['restored']
    assert (folder / 'audio/orphan.wav').read_bytes() == b'untouched'
    assert tx.review_quarantine('p')['items'][0]['status'] == 'restored'
    with pytest.raises(RuntimeError):
        tx.restore_quarantined('p', result['quarantine_name'])


def test_restore_never_overwrites_existing_media(monkeypatch, tmp_path):
    folder = setup(monkeypatch, tmp_path)
    result = tx.quarantine_preserved('p', 'receipt', 'audio/orphan.wav')
    (folder / 'audio/orphan.wav').write_bytes(b'new user data')
    with pytest.raises(RuntimeError, match='Unsafe'):
        tx.restore_quarantined('p', result['quarantine_name'])
    assert (folder / 'audio/orphan.wav').read_bytes() == b'new user data'
    assert tx.review_quarantine('p')['items'][0]['present']


def test_restore_refuses_unsafe_vault_and_pending_journal(monkeypatch, tmp_path):
    folder = setup(monkeypatch, tmp_path)
    result = tx.quarantine_preserved('p', 'receipt', 'audio/orphan.wav')
    tx.begin('p', 'next')
    with pytest.raises(RuntimeError, match='Pending'):
        tx.restore_quarantined('p', result['quarantine_name'])
    (folder / tx._NAME).unlink()
    original = folder / '.recovered-stems-quarantine'
    target = folder / 'moved'
    original.rename(target)
    original.symlink_to(target, target_is_directory=True)
    with pytest.raises(RuntimeError, match='Unsafe'):
        tx.restore_quarantined('p', result['quarantine_name'])


def test_restore_refuses_media_referenced_after_quarantine(monkeypatch, tmp_path):
    from types import SimpleNamespace
    folder = setup(monkeypatch, tmp_path)
    name = tx.quarantine_preserved('p', 'receipt', 'audio/orphan.wav')['quarantine_name']
    monkeypatch.setattr(tx, 'load_project', lambda _: SimpleNamespace(
        tracks=[SimpleNamespace(filename='orphan.wav')], clip_library=[]))
    with pytest.raises(RuntimeError, match='referenced'):
        tx.restore_quarantined('p', name)
    assert not (folder / 'audio/orphan.wav').exists()
    assert tx.review_quarantine('p')['items'][0]['present']


@pytest.mark.parametrize('invalid', [
    {'file': '../secrets', 'quarantine_name': 'safe'},
    {'file': 'audio/../secret', 'quarantine_name': 'safe'},
    {'file': 'audio/a.wav', 'quarantine_name': '../escape'},
])
def test_quarantine_audit_rejects_unsafe_paths(monkeypatch, tmp_path, invalid):
    import json
    folder = setup(monkeypatch, tmp_path)
    row = {'receipt': 'receipt', 'file': 'audio/orphan.wav',
           'quarantine_name': 'safe', 'status': 'quarantined'}
    row.update(invalid)
    (folder / tx._QUARANTINE).write_text(json.dumps({'version': 1, 'items': [row]}))
    with pytest.raises(RuntimeError, match='Invalid'):
        tx.review_quarantine('p')


def test_quarantine_audit_rejects_reused_identity(monkeypatch, tmp_path):
    import json
    folder = setup(monkeypatch, tmp_path)
    row = {'receipt': 'receipt', 'file': 'audio/orphan.wav',
           'quarantine_name': 'same', 'status': 'quarantined'}
    (folder / tx._QUARANTINE).write_text(json.dumps({'version': 1, 'items': [row, dict(row)]}))
    with pytest.raises(RuntimeError, match='Duplicate'):
        tx.review_quarantine('p')
