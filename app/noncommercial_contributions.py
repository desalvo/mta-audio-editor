"""Optional NC bank-transfer collection, with explicit manual evidence review.

No payment API, entitlement, invoice, debt or wallet mutation is performed.
An owner report is never proof of receipt. Administrator-confirmed external
receipts and reversals are append-only and conserve the frozen allocation.
"""
import hashlib
import csv
import io
import json
import re
import sqlite3
import time
import uuid

from . import auth
from .noncommercial_statements import user_statements
from .regime_operation_fence import FenceBlocked


def _hash(data):
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def _tables(c):
    return {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _actor(c,uid,*,admin=False):
    row=c.execute('SELECT role,active FROM users WHERE id=?',(uid,)).fetchone()
    if row is None or not row[1] or (admin and row[0]!='admin'):
        raise FenceBlocked('Active authorized account required')


def _epoch(c):
    from .service_regime import read_regime
    mirror=read_regime(auth.data_root()/'service-regime.json')
    row=c.execute('SELECT regime,revision,transitioning FROM regime_fence_state WHERE singleton=1').fetchone()
    if row is None or row[0]!='NON_COMMERCIAL' or row[2] or (mirror.regime.value,mirror.revision)!=tuple(row[:2]):
        raise FenceBlocked('NC collection requires its matching active non-commercial epoch')
    return row[1]


def initialize(c):
    if not c.in_transaction:raise FenceBlocked('NC collection requires a write transaction')
    expected={'nc_contribution_settings','nc_contribution_intents','nc_contribution_events'}
    present=_tables(c)&expected
    if present and present!=expected:raise FenceBlocked('Incomplete NC collection schema requires recovery')
    c.execute('''CREATE TABLE IF NOT EXISTS nc_contribution_settings(
      singleton INTEGER PRIMARY KEY CHECK(singleton=1),enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
      instructions TEXT NOT NULL,ledger_id TEXT NOT NULL,revision INTEGER NOT NULL)''')
    c.execute("INSERT OR IGNORE INTO nc_contribution_settings VALUES(1,0,'','',0)")
    c.execute('''CREATE TABLE IF NOT EXISTS nc_contribution_intents(
      id TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),request_id TEXT NOT NULL,
      period_start INTEGER NOT NULL,period_end INTEGER NOT NULL,statement_sha256 TEXT NOT NULL,
      amount_cents INTEGER NOT NULL CHECK(amount_cents>0),ledger_id TEXT NOT NULL,
      instructions TEXT NOT NULL,settings_revision INTEGER NOT NULL,regime_revision INTEGER NOT NULL,
      created_at INTEGER NOT NULL,payload_sha256 TEXT NOT NULL,UNIQUE(user_id,request_id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS nc_contribution_events(
      id TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),
      contribution_id TEXT NOT NULL REFERENCES nc_contribution_intents(id),request_id TEXT NOT NULL,
      kind TEXT NOT NULL CHECK(kind IN ('reported','cancelled','confirmed','reversed')),
      amount_cents INTEGER NOT NULL CHECK(amount_cents>=0),original_event_id TEXT,
      receipt_key TEXT UNIQUE,evidence_sha256 TEXT,actor_id INTEGER NOT NULL,
      created_at INTEGER NOT NULL,payload_sha256 TEXT NOT NULL,UNIQUE(actor_id,request_id))''')
    for table in ('nc_contribution_intents','nc_contribution_events'):
        c.execute(f'''CREATE TRIGGER IF NOT EXISTS {table}_immutable_update
          BEFORE UPDATE ON {table} BEGIN SELECT RAISE(ABORT,'Immutable NC collection'); END''')
        c.execute(f'''CREATE TRIGGER IF NOT EXISTS {table}_immutable_delete
          BEFORE DELETE ON {table} WHEN mta_nc_erasure('{table}',OLD.id)=0
          BEGIN SELECT RAISE(ABORT,'Immutable NC collection'); END''')


def settings(c):
    if 'nc_contribution_settings' not in _tables(c):
        return {'enabled':False,'instructions':'','ledger_id':'','revision':0}
    row=c.execute('SELECT enabled,instructions,ledger_id,revision FROM nc_contribution_settings WHERE singleton=1').fetchone()
    if row is None:raise FenceBlocked('Missing NC collection settings')
    return {'enabled':bool(row[0]),'instructions':row[1],'ledger_id':row[2],'revision':row[3]}


def configure(actor,body):
    if set(body)!={'enabled','instructions','ledger_id','expected_revision'} or type(body['enabled']) is not bool or type(body['expected_revision']) is not int:
        raise ValueError('Invalid collection configuration')
    instructions=body['instructions'];ledger=body['ledger_id']
    if not isinstance(instructions,str) or len(instructions)>2000 or any(ord(ch)<32 and ch not in '\n\t' for ch in instructions):raise ValueError('Invalid transfer instructions')
    if not isinstance(ledger,str) or (ledger and not re.fullmatch(r'[a-zA-Z0-9_-]{3,80}',ledger)) or (body['enabled'] and (not ledger or len(instructions.strip())<10)):
        raise ValueError('Enabled collection requires bank ledger identity and instructions')
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE');_actor(c,actor,admin=True)
        from .regime_operation_fence import initialize as initialize_fence
        initialize_fence(c);_epoch(c);initialize(c)
        old=settings(c)
        if old['revision']!=body['expected_revision']:raise FenceBlocked('Collection configuration changed')
        c.execute('UPDATE nc_contribution_settings SET enabled=?,instructions=?,ledger_id=?,revision=revision+1 WHERE singleton=1',
                  (int(body['enabled']),instructions.strip(),ledger))
        return settings(c)


def _request(value):
    if not isinstance(value,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{8,100}',value):raise ValueError('Invalid idempotency key')


def _verified(row):
    data=dict(row);digest=data.pop('payload_sha256')
    if digest!=_hash(data):raise FenceBlocked('NC collection payload integrity failed')
    return data


def _snapshot(c):
    tables=_tables(c)
    expected={'nc_contribution_settings','nc_contribution_intents','nc_contribution_events'}
    if not expected&tables:return []
    if not expected<=tables:raise FenceBlocked('Incomplete NC collection schema')
    intents=[_verified(row) for row in c.execute('SELECT * FROM nc_contribution_intents ORDER BY created_at,id')]
    result=[]
    for intent in intents:
        statements=user_statements(c,str(intent['user_id']))
        statement=next((s for s in statements if (s['start'],s['end'],s['sha256'])==(intent['period_start'],intent['period_end'],intent['statement_sha256'])),None)
        if statement is None:raise FenceBlocked('Contribution statement identity changed')
        events=[_verified(row) for row in c.execute('SELECT * FROM nc_contribution_events WHERE contribution_id=? ORDER BY created_at,id',(intent['id'],))]
        net=0;reported=False;cancelled=False;receipts={};reversed_amounts={}
        for event in events:
            if event['user_id']!=intent['user_id']:raise FenceBlocked('NC event owner mismatch')
            kind=event['kind'];amount=event['amount_cents']
            if cancelled and kind not in ('confirmed','reversed'):raise FenceBlocked('Owner declaration after cancellation')
            if kind in ('confirmed','reversed'):
                if type(amount) is not int or amount<=0 or not event['receipt_key'] or not re.fullmatch('[a-f0-9]{64}',event['evidence_sha256'] or ''):
                    raise FenceBlocked('Invalid external receipt evidence')
                if event['actor_id']==intent['user_id']:raise FenceBlocked('Self-verified external receipt')
                if kind=='confirmed':
                    if event['original_event_id'] is not None:raise FenceBlocked('Invalid receipt origin')
                    receipts[event['id']]=amount;net+=amount
                else:
                    original=event['original_event_id'];reversed_amounts[original]=reversed_amounts.get(original,0)+amount
                    if reversed_amounts[original]>receipts.get(original,0):raise FenceBlocked('Unproven or excessive receipt reversal')
                    net-=amount
            elif kind in ('reported','cancelled'):
                if amount or event['actor_id']!=intent['user_id'] or event['receipt_key'] or event['evidence_sha256'] or event['original_event_id']:
                    raise FenceBlocked('Invalid owner declaration')
                if kind=='reported':
                    if reported or net==intent['amount_cents']:raise FenceBlocked('Invalid repeated transfer report')
                    reported=True
                else:
                    prior=events[:events.index(event)]
                    if net or (prior and not receipts):raise FenceBlocked('Cannot cancel an unreviewed or retained transfer')
                    cancelled=True
            else:raise FenceBlocked('Unknown NC collection event')
            if net<0:raise FenceBlocked('Negative contribution net')
        allocated=0 if cancelled else min(net,intent['amount_cents']);excess=net-allocated
        state='refund_due' if excess else 'cancelled' if cancelled else 'received' if net==intent['amount_cents'] else 'partially_received' if net else 'pending_review' if reported else 'awaiting_transfer'
        result.append({**intent,'events':events,'received_cents':allocated,'net_received_cents':net,'excess_cents':excess,'remaining_cents':0 if cancelled else intent['amount_cents']-allocated,'state':state,'cancelled':cancelled,
                       'reported':reported,'can_cancel':not cancelled and (not events or bool(receipts) and net==0),'reversed_cents':sum(reversed_amounts.values()),'receipt_remaining':{key:value-reversed_amounts.get(key,0) for key,value in receipts.items()}})
    reserved={}
    for item in result:
        key=(item['user_id'],item['period_start'],item['period_end'])
        if not item['cancelled']:reserved[key]=reserved.get(key,0)+item['amount_cents']
        statement=next(s for s in user_statements(c,str(item['user_id'])) if (s['start'],s['end'])==key[1:])
        if reserved.get(key,0)>statement['contribution_cents']:raise FenceBlocked('Contribution reservations exceed frozen share')
    if c.execute('SELECT 1 FROM nc_contribution_events e LEFT JOIN nc_contribution_intents i ON i.id=e.contribution_id WHERE i.id IS NULL LIMIT 1').fetchone():
        raise FenceBlocked('Orphan NC receipt evidence')
    return result


def _put(c,table,data):
    # SQL identifiers and field order are fixed source definitions.
    digest=_hash(data);values=(*data.values(),digest)
    if table=='intent':
        c.execute('INSERT INTO nc_contribution_intents VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',values)
    else:c.execute('INSERT INTO nc_contribution_events VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',values)


def create(uid,body):
    if set(body)!={'start','end','statement_sha256','amount_cents','request_id','expected_settings_revision'}:raise ValueError('Invalid contribution request')
    if any(type(body[k]) is not int for k in ('start','end','amount_cents','expected_settings_revision')) or not 1<=body['amount_cents']<=10**9:raise ValueError('Invalid contribution amount')
    _request(body['request_id'])
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE');_actor(c,uid);epoch=_epoch(c);initialize(c)
        existing=_snapshot(c)
        old=next((i for i in existing if i['user_id']==uid and i['request_id']==body['request_id']),None)
        if old:
            if (old['period_start'],old['period_end'],old['statement_sha256'],old['amount_cents'],old['settings_revision'])!=(body['start'],body['end'],body['statement_sha256'],body['amount_cents'],body['expected_settings_revision']):raise FenceBlocked('Conflicting contribution retry')
            return _public(old)
        cfg=settings(c)
        if not cfg['enabled'] or cfg['revision']!=body['expected_settings_revision']:raise FenceBlocked('Contribution instructions unavailable or changed')
        statement=next((s for s in user_statements(c,str(uid)) if (s['start'],s['end'],s['sha256'])==(body['start'],body['end'],body['statement_sha256'])),None)
        if statement is None:raise FenceBlocked('Own frozen statement required')
        same=[i for i in existing if i['user_id']==uid and (i['period_start'],i['period_end'])==(body['start'],body['end']) and not i['cancelled']]
        if any(i['remaining_cents'] for i in same):raise FenceBlocked('Existing contribution must be resolved first')
        if sum(i['amount_cents'] for i in same)+body['amount_cents']>statement['contribution_cents']:raise FenceBlocked('Contribution exceeds unreserved cost share')
        data={'id':uuid.uuid4().hex,'user_id':uid,'request_id':body['request_id'],'period_start':body['start'],'period_end':body['end'],
              'statement_sha256':body['statement_sha256'],'amount_cents':body['amount_cents'],'ledger_id':cfg['ledger_id'],'instructions':cfg['instructions'],
              'settings_revision':cfg['revision'],'regime_revision':epoch,'created_at':time.time_ns()}
        _put(c,'intent',data)
        return _public(next(i for i in _snapshot(c) if i['id']==data['id']))


def _public(item,*,admin=False):
    keys=('id','period_start','period_end','statement_sha256','amount_cents','received_cents','net_received_cents','excess_cents','remaining_cents','state','instructions','reported','can_cancel','reversed_cents')
    result={k:item[k] for k in keys}
    result.update(voluntary=True,fiscal_receipt=False,verification_method='manual_external_bank_evidence',transfer_reference='MTA-NC-'+item['id'])
    result['events']=[{k:e[k] for k in ('id','kind','amount_cents','original_event_id','created_at')} for e in item['events']]
    if admin:
        result.update(user_id=item['user_id'],ledger_id=item['ledger_id'],receipt_remaining=item['receipt_remaining'])
        for public,private in zip(result['events'],item['events'],strict=True):
            public.update({k:private[k] for k in ('actor_id','evidence_sha256','receipt_key')})
    return result


def overview(c,uid=None):
    items=_snapshot(c);cfg=settings(c)
    from .service_regime import read_regime
    mirror=read_regime(auth.data_root()/'service-regime.json')
    fence=c.execute('SELECT regime,revision,transitioning FROM regime_fence_state WHERE singleton=1').fetchone() if 'regime_fence_state' in _tables(c) else None
    if (fence is not None and tuple(fence[:2])!=(mirror.regime.value,mirror.revision)) or (fence is None and (mirror.regime.value,mirror.revision)!=('NON_COMMERCIAL',0)):
        raise FenceBlocked('NC history regime mirror is inconsistent')
    active=mirror.regime.value=='NON_COMMERCIAL';writable=active and (fence is None or not fence[2])
    if uid is not None:
        items=[i for i in items if i['user_id']==uid]
        statements=user_statements(c,str(uid))
        for statement in statements:
            same=[i for i in items if (i['period_start'],i['period_end'])==(statement['start'],statement['end']) and not i['cancelled']]
            statement['reserved_cents']=sum(i['amount_cents'] for i in same)
            statement['received_cents']=sum(i['received_cents'] for i in same)
            statement['available_cents']=statement['contribution_cents']-statement['reserved_cents']
            statement['can_contribute']=writable and cfg['enabled'] and statement['available_cents']>0 and not any(i['remaining_cents'] for i in same)
        return {'regime':mirror.regime.value,'mutations_allowed':writable,'enabled':writable and cfg['enabled'],'settings_revision':cfg['revision'],'statements':statements,'contributions':[_public(i) for i in items]}
    from .noncommercial_statements import list_statements
    return {'regime':mirror.regime.value,'mutations_allowed':writable,'settings':cfg,'statements':list_statements(c),'contributions':[_public(i,admin=True) for i in items],
            'received_cents':sum(i['received_cents'] for i in items),'refund_due_cents':sum(i['excess_cents'] for i in items),'pending_count':sum(i['remaining_cents']>0 for i in items)}


def event(actor,contribution_id,body,*,admin=False):
    owner_fields={'kind','request_id'}
    admin_fields=owner_fields|{'amount_cents','external_reference','evidence_sha256','verified_external_receipt','original_event_id'}
    if set(body)!=(admin_fields if admin else owner_fields):raise ValueError('Invalid contribution event')
    kind=body['kind']
    if kind not in (('confirmed','reversed') if admin else ('reported','cancelled')):raise ValueError('Invalid contribution action')
    _request(body['request_id'])
    amount=body['amount_cents'] if admin else 0;receipt=None;evidence=None;original=None
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE');_actor(c,actor,admin=admin);epoch=_epoch(c);initialize(c)
        items=_snapshot(c);item=next((i for i in items if i['id']==contribution_id and (admin or i['user_id']==actor)),None)
        if item is None:raise ValueError('Contribution unavailable')
        if item['regime_revision']!=epoch:raise FenceBlocked('Contribution belongs to another regime epoch')
        if admin:
            if actor==item['user_id']:raise FenceBlocked('Another administrator must verify your transfer')
            reference=body['external_reference']
            if (type(amount) is not int or not 1<=amount<=10**9 or body['verified_external_receipt'] is not True
                or not isinstance(reference,str) or not re.fullmatch(r'[A-Za-z0-9 .:/_-]{6,140}',reference)
                or not isinstance(body['evidence_sha256'],str) or not re.fullmatch('[a-f0-9]{64}',body['evidence_sha256'])):
                raise ValueError('Positive amount and independently verified bank evidence required')
            receipt=_hash({'ledger_id':item['ledger_id'],'reference':''.join(reference.upper().split())});evidence=body['evidence_sha256'];original=body['original_event_id']
            if kind=='confirmed' and original is not None:raise ValueError('Receipt cannot reverse another event')
            if kind=='reversed' and not isinstance(original,str):raise ValueError('Original confirmed receipt required')
        old=next((e for i in items for e in i['events'] if e['actor_id']==actor and e['request_id']==body['request_id']),None)
        if old:
            if (old['contribution_id'],old['kind'],old['amount_cents'],old['original_event_id'],old['receipt_key'],old['evidence_sha256'])!=(contribution_id,kind,amount,original,receipt,evidence):raise FenceBlocked('Conflicting receipt retry')
            return _public(item,admin=admin)
        if item['cancelled'] and not admin:raise FenceBlocked('Cancelled contribution cannot receive owner declarations')
        if kind=='cancelled' and not item['can_cancel']:raise FenceBlocked('Reported or received transfers need administrator reconciliation')
        if kind=='reported' and (item['reported'] or not item['remaining_cents']):raise FenceBlocked('Transfer already reported or received')
        if kind=='reversed' and amount>item['receipt_remaining'].get(original,0):raise FenceBlocked('Reversal exceeds original verified receipt')
        data={'id':uuid.uuid4().hex,'user_id':item['user_id'],'contribution_id':contribution_id,'request_id':body['request_id'],
              'kind':kind,'amount_cents':amount,'original_event_id':original,'receipt_key':receipt,'evidence_sha256':evidence,'actor_id':actor,'created_at':time.time_ns()}
        _put(c,'event',data)
        return _public(next(i for i in _snapshot(c) if i['id']==contribution_id),admin=admin)


def audit(c):
    try:
        rows=_snapshot(c)
        return {'verified':True,'pending':sum(i['remaining_cents']>0 for i in rows),'refund_due_cents':sum(i['excess_cents'] for i in rows),'received_cents':sum(i['received_cents'] for i in rows),'transition_enabled':False}
    except (ValueError,TypeError,KeyError,FenceBlocked,OverflowError,sqlite3.DatabaseError):
        return {'verified':False,'pending':None,'refund_due_cents':None,'received_cents':None,'transition_enabled':False}


def export_csv(c,uid,language):
    if language not in ('it','en'):raise ValueError('Unsupported export language')
    data=overview(c,uid);output=io.StringIO(newline='');writer=csv.writer(output,lineterminator='\n')
    writer.writerow(('id_contributo','inizio','fine','sha256_consuntivo','contributo_centesimi','incasso_netto_centesimi','allocato_centesimi','rimborso_dovuto_centesimi','stato') if language=='it' else
                    ('contribution_id','start','end','statement_sha256','contribution_cents','net_received_cents','allocated_cents','refund_due_cents','state'))
    for item in data['contributions']:
        writer.writerow(tuple(item[k] for k in ('id','period_start','period_end','statement_sha256','amount_cents','net_received_cents','received_cents','excess_cents','state')))
    return {'format':'csv','currency':'EUR','fiscal_receipt':False,'verification_method':'manual_external_bank_evidence','content':output.getvalue()}


def authorize_account_erasure(c,uid,actor):
    tables=_tables(c)
    if not {'nc_contribution_intents','nc_period_statements'}&tables:return
    if not c.in_transaction:raise FenceBlocked('NC erasure requires a write transaction')
    allowed={}
    if 'nc_contribution_intents' in tables:
        allowed['nc_contribution_intents']={r[0] for r in c.execute('SELECT id FROM nc_contribution_intents WHERE user_id=?',(uid,))}
        allowed['nc_contribution_events']={r[0] for r in c.execute('SELECT id FROM nc_contribution_events WHERE user_id=?',(uid,))}
    if {'nc_period_statements','ai_compute_jobs'}<=tables:
        allowed['ai_compute_jobs']={r[0] for r in c.execute('SELECT id FROM ai_compute_jobs WHERE user_id=?',(uid,))}
    if not any(allowed.values()):return
    _actor(c,actor,admin=True)
    owner=c.execute('SELECT role,active FROM users WHERE id=?',(uid,)).fetchone()
    life=c.execute('SELECT state FROM account_lifecycle WHERE user_id=?',(uid,)).fetchone()
    if owner is None or owner[0]=='admin' or owner[1] or life is None or life[0] not in ('deleted','expired','erasing'):
        raise FenceBlocked('Approved retired-account erasure required')
    if {'nc_period_statements','ai_compute_jobs'}<=tables:
        from .noncommercial_period_guard import install_closed_period_guards
        install_closed_period_guards(c)
    c.create_function('mta_nc_erasure',2,lambda table,key:int(key in allowed.get(table,set())))
