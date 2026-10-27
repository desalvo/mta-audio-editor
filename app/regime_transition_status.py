"""Read-only complete transition lifecycle and exact precommit cancellation.

No diagnostic can authorize a cutover. Original commit/conservation receipts
control forward recovery; ambiguous or legacy commits retain their barrier.
"""
import sqlite3
import re

from . import auth
from .regime_admin_cutover import _actor, _row
from .regime_operation_fence import FenceBlocked, inspect
from .regime_service_lease import lease, enabled


def _record(con, row, tables):
    identifier, source, target, revision, evidence, status = row
    valid = source in ('NON_COMMERCIAL','COMMERCIAL') and target in ('NON_COMMERCIAL','COMMERCIAL') and source != target and type(revision) is int and revision >= 0
    valid &= isinstance(evidence,str) and re.fullmatch(r'[a-f0-9]{64}',evidence) is not None
    commit = con.execute('SELECT source,target,previous_revision,new_revision FROM regime_cutover_commits WHERE transition_id=?',(identifier,)).fetchone() if 'regime_cutover_commits' in tables else None
    final = con.execute('SELECT regime,revision FROM regime_cutover_finalizations WHERE transition_id=?',(identifier,)).fetchone() if 'regime_cutover_finalizations' in tables else None
    managed = _row(con,identifier) if 'regime_admin_cutovers' in tables else None
    phase = status
    if commit:
        valid &= tuple(commit)==(source,target,revision,revision+1) and status=='reserved'
        phase = 'committed'
    if final:
        valid &= bool(commit) and tuple(final)==(target,revision+1)
        phase = 'finalized'
    events = []
    if managed:
        valid &= (managed['source'],managed['target'],managed['source_revision'],managed['phase'])==(source,target,revision,phase)
        events = managed['events']
        valid &= [e['phase'] for e in events]==(['committed','finalized'] if phase=='finalized' else ['committed'])
    if 'regime_reservation_aborts' in tables:
        event=con.execute('SELECT actor_id,created_at,source_revision FROM regime_reservation_aborts WHERE transition_id=?',(identifier,)).fetchone()
        if event:
            valid &= status=='aborted' and not commit and event[2]==revision
            events.append({'phase':'aborted','actor_id':event[0],'created_at':event[1]})
    valid &= all(type(event.get('actor_id')) is int and event['actor_id']>0 and isinstance(event.get('created_at'),str) and re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.]+Z',event['created_at']) is not None for event in events)
    valid &= status in ('reserved','aborted')
    return {'id':identifier,'source':source,'target':target,'source_revision':revision,
            'revision':revision+1 if commit else revision,'phase':phase if valid else 'unverifiable',
            'verified':bool(valid),'barrier_held':phase=='committed','events':events,'actor_evidence_available':bool(events),
            'managed_recovery':bool(managed),'created_at':managed['created_at'] if managed else None,'action':None}


def overview(*, actor, offset=0, limit=25):
    if type(offset) is not int or offset<0 or type(limit) is not int or not 1<=limit<=100:
        raise ValueError('Invalid transition history page')
    with auth.db() as con:
        _actor(con,actor)
        con.execute('BEGIN')
        tables={r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        fence=inspect(con)
        if 'regime_transition_journal' in tables:
            rows=con.execute('SELECT * FROM regime_transition_journal ORDER BY rowid DESC LIMIT ? OFFSET ?',(limit,offset)).fetchall()
            total=con.execute('SELECT count(*) FROM regime_transition_journal').fetchone()[0]
            if 'regime_cutover_finalizations' in tables:
                pending=con.execute("SELECT * FROM regime_transition_journal j WHERE status='reserved' AND NOT EXISTS (SELECT 1 FROM regime_cutover_finalizations f WHERE f.transition_id=j.id) LIMIT 2").fetchall()
            else:
                pending=con.execute("SELECT * FROM regime_transition_journal WHERE status='reserved' LIMIT 2").fetchall()
        else:
            rows,pending,total=[],[],0
        items=[_record(con,row,tables) for row in rows]
        active=_record(con,pending[0],tables) if len(pending)==1 else None
        integrity=(len(pending)<=1 and bool(pending)==fence['transitioning'])
        integrity &= all(item['verified'] for item in items)
        if 'regime_cutover_commits' in tables and 'regime_transition_journal' in tables:
            integrity &= not con.execute('SELECT 1 FROM regime_cutover_commits c LEFT JOIN regime_transition_journal j ON j.id=c.transition_id WHERE j.id IS NULL LIMIT 1').fetchone()
        if 'regime_transition_journal' in tables:
            integrity &= not con.execute("SELECT 1 FROM regime_transition_journal WHERE typeof(source_revision)!='integer' OR source_revision<0 OR source_regime NOT IN ('COMMERCIAL','NON_COMMERCIAL') OR target_regime NOT IN ('COMMERCIAL','NON_COMMERCIAL') OR source_regime=target_regime LIMIT 1").fetchone()
        if 'regime_cutover_commits' in tables:
            integrity &= not con.execute('SELECT 1 FROM regime_cutover_commits GROUP BY new_revision HAVING count(*)>1 LIMIT 1').fetchone()
        reason=None
        if active:
            expected=(active['target'],active['revision']) if active['phase']=='committed' else (active['source'],active['source_revision'])
            integrity &= active['verified'] and (fence['regime'],fence['revision'])==expected
            if integrity and active['phase']=='reserved':
                active['action']='abort_reservation' if not any(fence['open_by_kind'].values()) else None
            elif integrity and active['phase']=='committed':
                integrity &= not any(fence['open_by_kind'].values())
                reason='recovery_mode_disabled' if active['managed_recovery'] else 'legacy_commit_requires_maintenance'
                if integrity and active['managed_recovery'] and enabled():
                    try:
                        from .regime_balance_continuity import verify
                        from .regime_cutover_mirror import inspect_mirror
                        verify(con,active['id'])
                        inspect_mirror(con,auth.data_root()/'service-regime.json',active['id'])
                        active['action']='forward_recovery'
                        reason=None
                    except (FenceBlocked,ValueError,sqlite3.DatabaseError,OSError):
                        reason='original_recovery_evidence_unverified'
            else:
                integrity=False
        if not integrity:
            reason='transition_integrity_unverified'
            if active:active['action']=None
        for item in items:
            if active and item['id']==active['id']:item['action']=active['action']
        return {'schema':'mta-transition-status-1','phase':('blocked' if not integrity else active['phase'] if active else 'idle'),
                'fence':fence,'active':active,'integrity_verified':bool(integrity),'reason':reason,
                'items':items,'total':total,'offset':offset,'transition_authorized':False}


def abort_reservation(*, actor, identifier, expected_revision, confirm):
    if confirm is not True or type(expected_revision) is not int or expected_revision<0 or not isinstance(identifier,str) or not 1<=len(identifier)<=120:
        raise ValueError('Exact reservation,revision and explicit confirmation required')
    with lease(exclusive=True), auth.db() as con:
        con.execute('BEGIN IMMEDIATE')
        _actor(con,actor)
        row=con.execute('SELECT status,source_revision FROM regime_transition_journal WHERE id=?',(identifier,)).fetchone()
        if row is None or row[1]!=expected_revision:
            raise FenceBlocked('Original reservation does not match')
        if con.execute("SELECT 1 FROM sqlite_master WHERE name='regime_cutover_commits'").fetchone() and con.execute('SELECT 1 FROM regime_cutover_commits WHERE transition_id=?',(identifier,)).fetchone():
            raise FenceBlocked('Committed transitions require forward recovery')
        from .regime_transition_journal import abort_verified
        if row[0]!='aborted':abort_verified(con,transition_id=identifier,expected_revision=expected_revision)
        # This table records only successful explicit precommit cancellation.
        con.execute('''CREATE TABLE IF NOT EXISTS regime_reservation_aborts(
            transition_id TEXT PRIMARY KEY REFERENCES regime_transition_journal(id),source_revision INTEGER NOT NULL,
            actor_id INTEGER NOT NULL,created_at TEXT NOT NULL DEFAULT(strftime('%Y-%m-%dT%H:%M:%fZ','now')))''')
        for action in ('UPDATE','DELETE'):
            # Fixed statements, no interpolated identifiers from the request.
            if action=='UPDATE':
                con.execute("CREATE TRIGGER IF NOT EXISTS regime_reservation_aborts_no_update BEFORE UPDATE ON regime_reservation_aborts BEGIN SELECT RAISE(ABORT,'Immutable reservation audit'); END")
            else:
                con.execute("CREATE TRIGGER IF NOT EXISTS regime_reservation_aborts_no_delete BEFORE DELETE ON regime_reservation_aborts BEGIN SELECT RAISE(ABORT,'Immutable reservation audit'); END")
        old=con.execute('SELECT source_revision FROM regime_reservation_aborts WHERE transition_id=?',(identifier,)).fetchone()
        if row[0]=='aborted' and old is None:
            raise FenceBlocked('Legacy cancellation cannot acquire an invented actor audit')
        if old is None:
            con.execute('INSERT INTO regime_reservation_aborts(transition_id,source_revision,actor_id) VALUES(?,?,?)',(identifier,expected_revision,actor))
        return {'aborted':True,'transition_id':identifier,'regime_mutated':False}
