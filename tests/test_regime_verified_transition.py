import sqlite3
import pytest
from app.regime_operation_fence import FenceBlocked, initialize, inspect
from app.regime_verified_transition import verified_reservation


def test_refuses_operator_supplied_clearance_on_incomplete_schema(tmp_path):
    connection = sqlite3.connect(tmp_path / 'state.sqlite', isolation_level=None)
    initialize(connection)
    connection.execute('BEGIN IMMEDIATE')
    try:
        with pytest.raises(FenceBlocked, match='reconciliation is incomplete'):
            verified_reservation(connection, transition_id='t1', target='COMMERCIAL', expected_revision=0)
        assert inspect(connection)['transitioning'] is False
    finally:
        connection.rollback()
        connection.close()


def test_refuses_stale_revision(tmp_path):
    connection = sqlite3.connect(tmp_path / 'state.sqlite', isolation_level=None)
    initialize(connection)
    connection.execute('BEGIN IMMEDIATE')
    try:
        with pytest.raises(FenceBlocked, match='revision conflict'):
            verified_reservation(connection, transition_id='t1', target='COMMERCIAL', expected_revision=1)
    finally:
        connection.rollback()
        connection.close()


def test_requires_caller_transaction(tmp_path):
    connection = sqlite3.connect(tmp_path / 'state.sqlite', isolation_level=None)
    initialize(connection)
    with pytest.raises(FenceBlocked, match='BEGIN IMMEDIATE'):
        verified_reservation(connection, transition_id='t1', target='COMMERCIAL', expected_revision=0)
    connection.close()
