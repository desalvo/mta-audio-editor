"""Actual admin maintenance cutover, original financial receipt and forward recovery.

Eligibility is deliberately narrower than the unfinished broad online provider
transition. No supplied callback, ready flag, snapshot or provider observation
can authorize this workflow. All decisions are recomputed under the service
lease and SQLite write transaction, using the explicit local readiness profile.
"""
import hashlib
import re

from . import auth
from .regime_balance_continuity import encode, commit_preserving_balances, finalize_preserving_balances, verify
from .regime_cutover_mirror import reconcile_mirror
from .regime_local_readiness import audit
from .regime_operation_fence import FenceBlocked
from .regime_service_lease import enabled
from .service_admission import cutover_guard
from .service_regime import Regime, read_regime, write_initial_noncommercial


def _actor(con, actor):
    if type(actor) is not int or actor <= 0 or not con.execute(
            "SELECT 1 FROM users WHERE id=? AND role='admin' AND active=1", (actor,)).fetchone():
        raise FenceBlocked('An active authenticated administrator is required')


def _initialize(con):
    con.execute('''CREATE TABLE IF NOT EXISTS regime_admin_cutovers(
        id TEXT PRIMARY KEY,actor_id INTEGER NOT NULL,source TEXT NOT NULL,target TEXT NOT NULL,
        source_revision INTEGER NOT NULL,preview_sha256 TEXT NOT NULL,
        phase TEXT NOT NULL CHECK(phase IN ('committed','finalized')),
        created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')))''')
    con.execute('''CREATE TRIGGER IF NOT EXISTS regime_admin_cutovers_immutable
        BEFORE UPDATE ON regime_admin_cutovers WHEN
        OLD.id IS NOT NEW.id OR OLD.actor_id IS NOT NEW.actor_id OR OLD.source IS NOT NEW.source OR
        OLD.target IS NOT NEW.target OR OLD.source_revision IS NOT NEW.source_revision OR
        OLD.preview_sha256 IS NOT NEW.preview_sha256 OR OLD.created_at IS NOT NEW.created_at OR
        OLD.phase!='committed' OR NEW.phase!='finalized'
        BEGIN SELECT RAISE(ABORT,'Immutable administrative transition'); END''')
    con.execute('''CREATE TRIGGER IF NOT EXISTS regime_admin_cutovers_no_delete
        BEFORE DELETE ON regime_admin_cutovers BEGIN SELECT RAISE(ABORT,'Immutable administrative transition'); END''')
    con.execute('''CREATE TABLE IF NOT EXISTS regime_admin_cutover_events(
        transition_id TEXT NOT NULL,phase TEXT NOT NULL CHECK(phase IN ('committed','finalized')),
        actor_id INTEGER NOT NULL,created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
        PRIMARY KEY(transition_id,phase),FOREIGN KEY(transition_id) REFERENCES regime_admin_cutovers(id))''')
    con.execute('''CREATE TRIGGER IF NOT EXISTS regime_admin_cutover_events_no_update
        BEFORE UPDATE ON regime_admin_cutover_events BEGIN SELECT RAISE(ABORT,'Immutable transition event'); END''')
    con.execute('''CREATE TRIGGER IF NOT EXISTS regime_admin_cutover_events_no_delete
        BEFORE DELETE ON regime_admin_cutover_events BEGIN SELECT RAISE(ABORT,'Immutable transition event'); END''')


def _preview(con, target, admission=None):
    target = Regime(target).value
    mirror = read_regime(auth.data_root() / 'service-regime.json')
    state = con.execute('SELECT regime,revision,transitioning FROM regime_fence_state WHERE singleton=1').fetchone()
    if state is None or tuple(state) != (mirror.regime.value, mirror.revision, 0):
        raise FenceBlocked('Service epoch mismatch or recovery required')
    from .regime_transition_journal import inspect_reservations
    if not inspect_reservations(con)['integrity_verified']:
        raise FenceBlocked('Original transition journal is inconsistent')
    if target == state[0]:
        raise FenceBlocked('Requested regime is already active')
    proof = audit(con)
    if admission is not None:
        proof = {**proof, 'service_admission': admission}
    body = {'source': state[0], 'target': target, 'source_revision': state[1], 'readiness': proof}
    return body | {'preview_sha256': hashlib.sha256(encode(body).encode()).hexdigest(), 'transition_enabled': True}


def preview(*, target, actor):
    if not enabled():
        raise FenceBlocked('Local-authority cutover is not enabled')
    with cutover_guard(actor=actor) as admission, auth.db() as con:
        con.execute('BEGIN IMMEDIATE')
        _actor(con, actor)
        return _preview(con, target, admission)


def _row(con, identifier):
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name='regime_admin_cutovers'").fetchone():
        return None
    row = con.execute('SELECT * FROM regime_admin_cutovers WHERE id=?', (identifier,)).fetchone()
    if not row:
        return None
    return dict(row) | {'events': [dict(r) for r in con.execute(
        'SELECT phase,actor_id,created_at FROM regime_admin_cutover_events WHERE transition_id=? ORDER BY rowid', (identifier,))]}


def _public(row):
    return {**row, 'revision': row['source_revision'] + 1,
            'barrier_held': row['phase'] != 'finalized', 'financial_records_mutated': False,
            'recovery_action': 'forward' if row['phase'] != 'finalized' else None}


def _finish(identifier, actor):
    # The caller retains the exclusive lease across both database transactions
    # and the durable mirror replacement. A crash retains the persistent barrier.
    with auth.db() as con:
        con.execute('BEGIN IMMEDIATE')
        _actor(con, actor)
        row = _row(con, identifier)
        if row is None:
            raise FenceBlocked('Unknown administrative cutover')
        if row['phase'] == 'finalized':
            return _public(row)
        state = con.execute('SELECT regime,revision,transitioning FROM regime_fence_state WHERE singleton=1').fetchone()
        if tuple(state or ()) != (row['target'], row['source_revision'] + 1, 1):
            raise FenceBlocked('Committed cutover epoch is inconsistent')
        verify(con, identifier)
        audit(con)
        path = auth.data_root() / 'service-regime.json'
        reconcile_mirror(con, path, identifier)
        def ready(connection):
            audit(connection)
            return True
        result = finalize_preserving_balances(con, mirror_path=path, transition_id=identifier, readiness_check=ready)
        con.execute("UPDATE regime_admin_cutovers SET phase='finalized' WHERE id=? AND phase='committed'", (identifier,))
        con.execute("INSERT INTO regime_admin_cutover_events(transition_id,phase,actor_id) VALUES(?,'finalized',?)", (identifier, actor))
        return _public(_row(con, identifier)) | result


def execute(*, identifier, target, expected_revision, preview_sha256, confirm, actor):
    if (not isinstance(identifier, str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,100}', identifier) or
            type(expected_revision) is not int or expected_revision < 0 or confirm is not True or
            not isinstance(preview_sha256, str) or not re.fullmatch('[a-f0-9]{64}', preview_sha256)):
        raise ValueError('Explicit confirmation, exact preview and transition identity required')
    target = Regime(target).value
    if not enabled():
        raise FenceBlocked('Local-authority cutover is not enabled')
    # A finalized original request is read-only even after explicit reopening.
    # Requiring another drain for this receipt would break response-loss replay.
    from .service_admission import control
    with control(), auth.db() as con:
        _actor(con, actor)
        old = _row(con, identifier)
        if old and old['phase'] == 'finalized':
            if (old['actor_id'], old['target'], old['source_revision'], old['preview_sha256']) != (
                    actor, target, expected_revision, preview_sha256):
                raise FenceBlocked('Administrative cutover identity replay conflict')
            return _public(old)
    with cutover_guard(actor=actor, recovering=identifier) as admission:
        with auth.db() as con:
            con.execute('BEGIN IMMEDIATE')
            _actor(con, actor)
            old = _row(con, identifier)
            if old:
                if (old['actor_id'], old['target'], old['source_revision'], old['preview_sha256']) != (
                        actor, target, expected_revision, preview_sha256):
                    raise FenceBlocked('Administrative cutover identity replay conflict')
            else:
                review = _preview(con, target, admission)
                if review['source_revision'] != expected_revision or review['preview_sha256'] != preview_sha256:
                    raise FenceBlocked('Preview is stale; inspect and confirm again')
                # Default NC mirrors are provisioned before committing SQLite,
                # never invented during recovery after an already committed cut.
                path = auth.data_root() / 'service-regime.json'
                if not path.exists():
                    write_initial_noncommercial(path)
                _initialize(con)
                from .regime_transition_journal import reserve
                reserve(con, transition_id=identifier, target=target, expected_revision=expected_revision,
                        evidence={'ready': True, 'unresolved': [], 'source': review['readiness']['profile'],
                                  'snapshot_sha256': preview_sha256})
                def ready(connection):
                    audit(connection)
                    return True
                commit_preserving_balances(con, transition_id=identifier, expected_revision=expected_revision,
                                           readiness_check=ready)
                con.execute('''INSERT INTO regime_admin_cutovers
                    (id,actor_id,source,target,source_revision,preview_sha256,phase) VALUES(?,?,?,?,?,?,'committed')''',
                    (identifier, actor, review['source'], target, expected_revision, preview_sha256))
                con.execute("INSERT INTO regime_admin_cutover_events(transition_id,phase,actor_id) VALUES(?,'committed',?)", (identifier, actor))
        return _finish(identifier, actor)


def recover(*, identifier, expected_revision, confirm, actor):
    if not enabled() or confirm is not True or type(expected_revision) is not int or expected_revision < 1:
        raise FenceBlocked('Enabled local-authority recovery and explicit epoch confirmation required')
    with cutover_guard(actor=actor, recovering=identifier), auth.db() as con:
        _actor(con, actor)
        row = _row(con, identifier)
        if row is None or row['source_revision'] + 1 != expected_revision:
            raise FenceBlocked('Recovery identity or epoch does not match')
        # Close the read transaction before the transaction-owning finalizer.
        con.commit()
        return _finish(identifier, actor)


def history(*, actor, limit=25, offset=0):
    if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or offset < 0:
        raise ValueError('Invalid audit page')
    with auth.db() as con:
        _actor(con, actor)
        if not con.execute("SELECT 1 FROM sqlite_master WHERE name='regime_admin_cutovers'").fetchone():
            return {'items': [], 'total': 0}
        return {'items': [_public(_row(con, r[0])) for r in con.execute(
            'SELECT id FROM regime_admin_cutovers ORDER BY rowid DESC LIMIT ? OFFSET ?', (limit, offset))],
            'total': con.execute('SELECT COUNT(*) FROM regime_admin_cutovers').fetchone()[0]}


def status(*, identifier, actor):
    with auth.db() as con:
        _actor(con, actor)
        row = _row(con, identifier)
        return _public(row) if row else None
