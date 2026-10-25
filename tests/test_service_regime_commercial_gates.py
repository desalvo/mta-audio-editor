import pytest
from app import auth
from app.service_regime import RegimeError, require_commercial, current_regime


def test_nc_rejects_commercial_without_creating_db(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, 'DATA_ROOT', tmp_path)
    assert current_regime().value == 'NON_COMMERCIAL'
    with pytest.raises(RegimeError, match='NON_COMMERCIAL'):
        require_commercial('credits')
    assert not (tmp_path/'auth.sqlite3').exists()


def test_commercial_gate_can_be_read_from_explicit_existing_mode(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, 'DATA_ROOT', tmp_path)
    (tmp_path/'service-regime.json').write_text('{"regime":"COMMERCIAL","revision":1}')
    from app.regime_operation_fence import initialize
    import sqlite3
    with sqlite3.connect(auth.db_path()) as connection:
        initialize(connection, initial_regime='COMMERCIAL')
        connection.execute('UPDATE regime_fence_state SET revision=1')
    require_commercial('credits')


def test_corrupt_configuration_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, 'DATA_ROOT', tmp_path)
    (tmp_path/'service-regime.json').write_text('{}')
    with pytest.raises(RegimeError):require_commercial()
