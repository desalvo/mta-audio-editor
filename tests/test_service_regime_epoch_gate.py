import json
import sqlite3

import pytest

from app import auth
from app.regime_operation_fence import initialize
from app.service_regime import RegimeError, current_regime, require_commercial


def test_default_noncommercial_without_db(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, 'DATA_ROOT', tmp_path)
    assert current_regime().value == 'NON_COMMERCIAL'
    assert not auth.db_path().exists()


def test_commercial_without_fence_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, 'DATA_ROOT', tmp_path)
    (tmp_path / 'service-regime.json').write_text(json.dumps({'regime': 'COMMERCIAL', 'revision': 0}))
    with pytest.raises(RegimeError, match='initialized fence'):
        require_commercial()


def test_matching_commercial_fence(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, 'DATA_ROOT', tmp_path)
    (tmp_path / 'service-regime.json').write_text(json.dumps({'regime': 'COMMERCIAL', 'revision': 0}))
    with sqlite3.connect(auth.db_path()) as connection:
        initialize(connection, initial_regime='COMMERCIAL')
    require_commercial()


@pytest.mark.parametrize('change', ['transition', 'revision', 'regime'])
def test_mismatch_refuses_commercial(tmp_path, monkeypatch, change):
    monkeypatch.setattr(auth, 'DATA_ROOT', tmp_path)
    (tmp_path / 'service-regime.json').write_text(json.dumps({'regime': 'COMMERCIAL', 'revision': 0}))
    with sqlite3.connect(auth.db_path()) as connection:
        initialize(connection, initial_regime='COMMERCIAL')
        if change == 'transition':
            connection.execute('UPDATE regime_fence_state SET transitioning=1')
        elif change == 'revision':
            connection.execute('UPDATE regime_fence_state SET revision=1')
        else:
            connection.execute("UPDATE regime_fence_state SET regime='NON_COMMERCIAL'")
    with pytest.raises(RegimeError):
        require_commercial()


def test_fence_retries_transient_read_only_sqlite_contention(tmp_path, monkeypatch):
    import sqlite3
    from app import runtime_paths, service_regime
    db = tmp_path / 'auth.sqlite3'
    db.touch()
    monkeypatch.setattr(runtime_paths, 'policy_paths', lambda: (tmp_path, db))
    connect = sqlite3.connect
    attempts = []

    def open_database(*args, **kwargs):
        attempts.append(args[0])
        if len(attempts) == 1:
            raise sqlite3.OperationalError('database is locked')
        return connect(*args, **kwargs)

    monkeypatch.setattr(sqlite3, 'connect', open_database)
    assert service_regime.current_regime() == service_regime.Regime.NON_COMMERCIAL
    assert attempts == [db.as_uri() + '?mode=ro'] * 2


def test_fence_does_not_retry_a_damaged_database(tmp_path, monkeypatch):
    from app import runtime_paths, service_regime
    db = tmp_path / 'auth.sqlite3'
    db.write_bytes(b'invalid database contents')
    monkeypatch.setattr(runtime_paths, 'policy_paths', lambda: (tmp_path, db))
    with pytest.raises(service_regime.RegimeError, match='unavailable or damaged'):
        service_regime.current_regime()
