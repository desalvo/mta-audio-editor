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
