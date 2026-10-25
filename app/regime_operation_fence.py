"""Durable, fail-closed operation fence for service-regime transitions.

This module supplies the transactional primitive; callers must enroll all job,
checkout, and webhook entry paths before enabling service-regime transitions.
No timestamp automatically releases an external-payment operation.
"""
from __future__ import annotations

import sqlite3


class FenceBlocked(RuntimeError):
    pass


_SCHEMA = """
CREATE TABLE IF NOT EXISTS regime_fence_state (
  singleton INTEGER PRIMARY KEY CHECK(singleton=1),
  regime TEXT NOT NULL CHECK(regime IN ('NON_COMMERCIAL','COMMERCIAL')),
  revision INTEGER NOT NULL CHECK(revision>=0),
  transitioning INTEGER NOT NULL DEFAULT 0 CHECK(transitioning IN (0,1))
);
CREATE TABLE IF NOT EXISTS regime_fence_operations (
  operation_id TEXT PRIMARY KEY,
  kind TEXT NOT NULL CHECK(kind IN ('job','checkout','webhook')),
  regime TEXT NOT NULL CHECK(regime IN ('NON_COMMERCIAL','COMMERCIAL')),
  revision INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','closed'))
);
CREATE INDEX IF NOT EXISTS idx_regime_fence_open ON regime_fence_operations(status);
"""


def initialize(connection: sqlite3.Connection, *, initial_regime: str = 'NON_COMMERCIAL') -> None:
    if initial_regime not in {'NON_COMMERCIAL', 'COMMERCIAL'}:
        raise ValueError('Invalid initial regime')
    # executescript() commits a pending transaction implicitly in sqlite3.
    # Preserve transaction ownership so callers can initialize the fence in
    # the same BEGIN IMMEDIATE as checkout/job admission.
    for statement in _SCHEMA.split(';'):
        if statement.strip():
            connection.execute(statement)
    connection.execute('INSERT OR IGNORE INTO regime_fence_state(singleton,regime,revision) VALUES(1,?,0)',(initial_regime,))


def _require_transaction(connection: sqlite3.Connection) -> None:
    if not connection.in_transaction:
        raise FenceBlocked('BEGIN IMMEDIATE transaction required')


def admit(connection: sqlite3.Connection, operation_id: str, kind: str, *, required_regime: str | None = None) -> dict:
    """Idempotently enroll operation inside caller-owned BEGIN IMMEDIATE transaction."""
    _require_transaction(connection)
    if not isinstance(operation_id, str) or not 1 <= len(operation_id) <= 160 or kind not in {'job','checkout','webhook'}:
        raise ValueError('Invalid operation identity or kind')
    row = connection.execute('SELECT regime,revision,transitioning FROM regime_fence_state WHERE singleton=1').fetchone()
    if row is None or row[2]:
        raise FenceBlocked('Service regime transition in progress or uninitialized')
    if required_regime is not None and row[0] != required_regime:
        raise FenceBlocked('Operation not permitted in active regime')
    old = connection.execute('SELECT kind,regime,revision,status FROM regime_fence_operations WHERE operation_id=?',(operation_id,)).fetchone()
    if old is not None:
        if old[0] != kind:
            raise FenceBlocked('Conflicting operation identity')
        if required_regime is not None and old[1] != required_regime:
            raise FenceBlocked('Existing operation has incompatible original regime')
        if (old[1], old[2]) != (row[0], row[1]) and old[3] == 'open':
            raise FenceBlocked('Open operation belongs to a different regime epoch')
        return dict(operation_id=operation_id,kind=old[0],regime=old[1],revision=old[2],status=old[3])
    connection.execute('INSERT INTO regime_fence_operations(operation_id,kind,regime,revision) VALUES(?,?,?,?)',(operation_id,kind,row[0],row[1]))
    return dict(operation_id=operation_id,kind=kind,regime=row[0],revision=row[1],status='open')


def settle(connection: sqlite3.Connection, operation_id: str) -> None:
    _require_transaction(connection)
    changed = connection.execute("UPDATE regime_fence_operations SET status='closed' WHERE operation_id=? AND status='open'",(operation_id,)).rowcount
    if not changed and connection.execute('SELECT 1 FROM regime_fence_operations WHERE operation_id=?',(operation_id,)).fetchone() is None:
        raise FenceBlocked('Unknown operation; cannot settle')


def begin_transition(connection: sqlite3.Connection, *, expected_revision: int, target: str) -> dict:
    """Reserve a transition only when every tracked operation has settled.

    This does NOT change the active regime; financial reconciliation and the
    external configuration commit are separate, intentionally disabled steps.
    """
    _require_transaction(connection)
    if target not in {'NON_COMMERCIAL','COMMERCIAL'}:
        raise ValueError('Invalid regime')
    row = connection.execute('SELECT regime,revision,transitioning FROM regime_fence_state WHERE singleton=1').fetchone()
    if row is None or row[2] or row[1] != expected_revision:
        raise FenceBlocked('Transition revision conflict or already in progress')
    open_count=connection.execute("SELECT COUNT(*) FROM regime_fence_operations WHERE status='open'").fetchone()[0]
    if open_count:
        raise FenceBlocked(f'{open_count} unsettled operation(s) block transition')
    if target == row[0]:
        raise FenceBlocked('Regime already active')
    connection.execute('UPDATE regime_fence_state SET transitioning=1 WHERE singleton=1')
    return {'from':row[0], 'to':target,'revision':row[1], 'reserved':True}


def abort_transition(connection: sqlite3.Connection) -> None:
    _require_transaction(connection)
    connection.execute('UPDATE regime_fence_state SET transitioning=0 WHERE singleton=1')


def inspect(connection: sqlite3.Connection) -> dict:
    """Read-only diagnostic snapshot; never imply that uninstrumented entries are safe."""
    state = connection.execute('SELECT regime,revision,transitioning FROM regime_fence_state WHERE singleton=1').fetchone()
    if state is None:
        raise FenceBlocked('Operation fence not initialized')
    by_kind = dict(connection.execute("SELECT kind,COUNT(*) FROM regime_fence_operations WHERE status='open' GROUP BY kind"))
    return {'regime': state[0], 'revision': state[1], 'transitioning': bool(state[2]),
            'open_by_kind': {kind: by_kind.get(kind, 0) for kind in ('job','checkout','webhook')},
            'all_entry_points_instrumented': False, 'transition_enabled': False}


def validate_receipt(connection: sqlite3.Connection, operation_id: str, *, kind: str, regime: str, revision: int) -> dict:
    """Ensure asynchronous replies are resolved against original admission epoch."""
    row = connection.execute('SELECT kind,regime,revision,status FROM regime_fence_operations WHERE operation_id=?', (operation_id,)).fetchone()
    if row is None or row[0] != kind or row[1] != regime or row[2] != revision:
        raise FenceBlocked('Operation receipt not found or mismatched')
    return {'operation_id': operation_id, 'kind': row[0], 'regime': row[1], 'revision': row[2], 'status': row[3]}


def execute_atomic(connection: sqlite3.Connection, operation_id: str, kind: str, action, *,
                   required_regime: str | None = None):
    """Atomically admit and apply one *database-local* operation.

    The callback must use this exact connection, must not commit/rollback, and
    must not perform external network calls. Closed IDs are not applied twice.
    External payment events require a durable provider-event inbox separately.
    """
    if connection.in_transaction:
        raise FenceBlocked('execute_atomic owns its transaction')
    connection.execute('BEGIN IMMEDIATE')
    try:
        initialize_existing = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='regime_fence_state'"
        ).fetchone()
        if not initialize_existing:
            raise FenceBlocked('Operation fence has not been initialized')
        receipt = admit(connection, operation_id, kind, required_regime=required_regime)
        if receipt['status'] == 'closed':
            connection.commit()
            return {'applied': False, 'receipt': receipt, 'result': None}
        result = action(connection, receipt)
        if connection.in_transaction is False:
            raise FenceBlocked('Callback changed transaction ownership')
        settle(connection, operation_id)
        connection.commit()
        receipt['status'] = 'closed'
        return {'applied': True, 'receipt': receipt, 'result': result}
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise

# Durable provider inbox. The business mutation and marking an event applied
# must be performed by the same SQLite connection in one write transaction.
_INBOX_SCHEMA = """
CREATE TABLE IF NOT EXISTS regime_provider_inbox (
 provider TEXT NOT NULL,
 event_id TEXT NOT NULL,
 operation_id TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('received','applied')),
 PRIMARY KEY(provider,event_id)
);
"""


def apply_provider_event(connection: sqlite3.Connection, *, provider: str, event_id: str,
                         operation_id: str, payload_sha256: str, action):
    """Apply an authenticated external event at most once.

    Authentication/signature verification MUST be done by the provider handler
    before calling this function. ``action`` changes only this SQLite database,
    must not commit, and must validate the original operation's receipt and
    permitted economic status before altering balances. This function does not
    make a remote network call or settle the originating checkout automatically.
    """
    import re
    if connection.in_transaction:
        raise FenceBlocked('Provider inbox owns its transaction')
    if provider not in {'stripe', 'paypal'} or not isinstance(event_id, str) or not (1 <= len(event_id) <= 200):
        raise ValueError('Invalid provider event identity')
    if not isinstance(operation_id, str) or not (1 <= len(operation_id) <= 160):
        raise ValueError('Invalid originating operation')
    if not isinstance(payload_sha256, str) or re.fullmatch(r'[a-f0-9]{64}', payload_sha256) is None:
        raise ValueError('Invalid event payload digest')
    connection.execute('BEGIN IMMEDIATE')
    try:
        # Initialization and admission are deliberately separate, explicit steps.
        if connection.execute("SELECT name FROM sqlite_master WHERE name='regime_fence_state'").fetchone() is None:
            raise FenceBlocked('Operation fence not initialized')
        connection.execute(_INBOX_SCHEMA)
        old = connection.execute(
            'SELECT operation_id,payload_sha256,state FROM regime_provider_inbox WHERE provider=? AND event_id=?',
            (provider, event_id)).fetchone()
        if old is not None and (old[0] != operation_id or old[1] != payload_sha256):
            raise FenceBlocked('Provider event identity reused with conflicting payload')
        if old is not None and old[2] == 'applied':
            connection.commit()
            return {'applied': False, 'duplicate': True}
        receipt = connection.execute(
            'SELECT kind,regime,revision,status FROM regime_fence_operations WHERE operation_id=?',
            (operation_id,)).fetchone()
        if receipt is None or receipt[0] != 'checkout':
            raise FenceBlocked('Missing enrolled checkout for provider event')
        if receipt[1] != 'COMMERCIAL':
            raise FenceBlocked('Provider payment cannot settle a noncommercial checkout')
        if old is None:
            connection.execute(
                "INSERT INTO regime_provider_inbox(provider,event_id,operation_id,payload_sha256,state) VALUES(?,?,?,?,'received')",
                (provider,event_id,operation_id,payload_sha256))
        result = action(connection, {'operation_id': operation_id, 'regime': receipt[1],
                                     'revision': receipt[2], 'status': receipt[3]})
        if not connection.in_transaction:
            raise FenceBlocked('Provider action changed transaction ownership')
        connection.execute("UPDATE regime_provider_inbox SET state='applied' WHERE provider=? AND event_id=?",
                           (provider,event_id))
        connection.commit()
        return {'applied': True, 'duplicate': False, 'result': result}
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise


def audit_unfenced_metered_jobs(connection: sqlite3.Connection) -> dict:
    """Fail-closed read-only coverage audit for active metered AI jobs.

    Legacy jobs are intentionally not silently enrolled: their original
    regime/revision is unknown and requires operator reconciliation.
    """
    table_names = {row[0] for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    if 'ai_compute_jobs' not in table_names or 'regime_fence_operations' not in table_names:
        return {'verified': False, 'unfenced_count': None,
                'reason': 'required accounting or fence table missing'}
    columns = {row[1] for row in connection.execute('PRAGMA table_info(ai_compute_jobs)')}
    if not {'id', 'status'} <= columns:
        return {'verified': False, 'unfenced_count': None,
                'reason': 'accounting schema incomplete'}
    # The fence operation is always job:<ledger id>; a closed fence for an
    # active job is also a discrepancy, not proof of its safe completion.
    count = connection.execute('''
        SELECT COUNT(*) FROM ai_compute_jobs AS j
        LEFT JOIN regime_fence_operations AS f
          ON f.operation_id = 'job:ledger:' || j.id AND f.kind = 'job'
        WHERE j.status NOT IN ('completed','failed','cancelled','canceled','refunded')
          AND (f.operation_id IS NULL OR f.status != 'open')
    ''').fetchone()[0]
    return {'verified': True, 'unfenced_count': count, 'ready': count == 0}
