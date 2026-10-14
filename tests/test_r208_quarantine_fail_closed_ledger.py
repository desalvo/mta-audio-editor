"""Quarantine must validate durable bookkeeping before changing user media."""
import json
from types import SimpleNamespace
import pytest
from app import ai_recovered_stem_transaction as tx


def test_invalid_quarantine_ledger_does_not_move_media(monkeypatch, tmp_path):
    folder = tmp_path / 'project'
    (folder / 'audio').mkdir(parents=True)
    (folder / 'originals').mkdir()
    monkeypatch.setattr(tx, 'pdir', lambda _: folder)
    monkeypatch.setattr(tx, 'load_project', lambda _: SimpleNamespace(tracks=[], clip_library=[], recovered_ai_imports=[]))
    tx.begin('p', 'req')
    source = folder / 'audio' / 'orphan.wav'
    source.write_bytes(b'important')
    tx.reconcile('p')
    (folder / tx._QUARANTINE).write_text(json.dumps({'version': 1, 'items': [{'invalid': True}]}))
    with pytest.raises(RuntimeError, match='Invalid quarantine audit item'):
        tx.quarantine_preserved('p', 'req', 'audio/orphan.wav')
    assert source.read_bytes() == b'important'
    vault = folder / '.recovered-stems-quarantine'
    assert not any(vault.iterdir())
