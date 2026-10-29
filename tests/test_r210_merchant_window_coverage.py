import sqlite3

import pytest
from app import paypal_merchant_history as h
from scripts.audit_merchant_coverage import audit, main

F = 'a'*64


@pytest.fixture
def book():
    with sqlite3.connect(':memory:') as c:
        c.row_factory = sqlite3.Row
        h.initialize(c)
        yield c


def add(c, start, end, *, fingerprint=F, environment='sandbox', data=None):
    data = [] if data is None else data
    a, b = f'2026-09-{start:02d}T00:00:00Z', f'2026-09-{end:02d}T00:00:00Z'
    sha = h.digest(data); identity = h.digest([environment, fingerprint, a, b, sha])
    c.execute('INSERT INTO paypal_merchant_history VALUES(?,?,?,?,?,?,?,?,?)',
              (identity, environment, fingerprint, a, b, h.encode(data), sha, 1, 1))


def read(c): return audit(c, '2026-09-01T00:00:00Z', '2026-09-05T00:00:00Z', 'sandbox', F)


@pytest.mark.parametrize('windows,covered,gaps', [([], False, 1), ([(1,5)], True, 0),
    ([(1,3),(3,5)], True, 0), ([(1,4),(2,5)], True, 0),
    ([(1,2),(3,5)], False, 1), ([(2,4)], False, 2), ([(5,6)], False, 1)])
def test_exact_window_union_never_infers_missing_intervals(book, windows, covered, gaps):
    for a,b in windows: add(book,a,b)
    result = read(book)
    assert result['requested_window_covered'] is covered and len(result['gaps']) == gaps
    assert not any(result[k] for k in ['complete_account_history','ledger_reconciled','transition_authorized','release_candidate'])
    assert result == read(book)


@pytest.mark.parametrize('change', ['merchant','environment'])
def test_foreign_observations_cannot_cover_gap(book, change):
    add(book,1,5,**({'fingerprint':'b'*64} if change=='merchant' else {'environment':'live'}))
    assert not read(book)['requested_window_covered']


def test_corrupted_snapshot_is_not_filtered_away(book):
    add(book,1,5,fingerprint='b'*64)
    book.execute('DROP TRIGGER paypal_merchant_history_immutable')
    book.execute("UPDATE paypal_merchant_history SET evidence_json='{}'")
    with pytest.raises((ValueError, h.FenceBlocked)):read(book)


def test_missing_database_is_not_created(tmp_path, monkeypatch, capsys):
    path = tmp_path/'absent.db'
    monkeypatch.setattr('sys.argv',['audit','--database',str(path),'--start','2026-09-01T00:00:00Z',
        '--end','2026-09-05T00:00:00Z','--environment','sandbox','--fingerprint',F])
    assert main()==1 and not path.exists()
    assert 'unavailable' in capsys.readouterr().err


def test_changed_same_window_is_not_accepted_as_coverage(book):
    from test_r210_paypal_merchant_history import record
    add(book,1,5)
    add(book,1,5,data=[h.normalize(record())])
    result=read(book)
    assert not result['requested_window_covered'] and len(result['conflicting_windows'])==1


def test_cli_reads_existing_database_without_modifying_bytes(tmp_path,monkeypatch,capsys):
    path=tmp_path/'book.db'
    with sqlite3.connect(path) as c:
        h.initialize(c);add(c,1,5)
    before=path.read_bytes()
    monkeypatch.setattr('sys.argv',['audit','--database',str(path),'--start','2026-09-01T00:00:00Z',
        '--end','2026-09-05T00:00:00Z','--environment','sandbox','--fingerprint',F])
    assert main()==0 and '"requested_window_covered": true' in capsys.readouterr().out
    assert path.read_bytes()==before
