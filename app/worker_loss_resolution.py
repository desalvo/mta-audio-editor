"""Explicit operator-funded loss after verified local worker termination.

Unknown consumption remains unknown. An approved contractual no-charge outcome
releases reservations atomically; it is not a zero-use measurement or money
transfer. Frozen evidence and legacy uncertainty require ordinary recovery.
"""
import hashlib
import json
import re
import sqlite3
import time
import uuid

from . import auth, worker_cgroup_recovery as processes
from .regime_operation_fence import FenceBlocked


def _columns(c):
    return {r[1] for r in c.execute('PRAGMA table_info(ai_compute_jobs)')}


def assert_not_resolved(c, job_id):
    if 'operator_loss_id' not in _columns(c):return
    row=c.execute('SELECT operator_loss_id FROM ai_compute_jobs WHERE id=?',(job_id,)).fetchone()
    if row and row[0]:raise FenceBlocked('Operator loss is final; no new execution, publication or metering')


def mark_evidence(job_id, worker_id, token):
    """Commit before any owned immutable metering/publication/outbox write."""
    from .deferred_execution_owner import validate_receipt
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE')
        validate_receipt(c,job_id,worker_id,token,allow_finished=True)
        note_evidence_in_transaction(c,job_id)


def note_evidence_in_transaction(c,job_id):
    if not c.in_transaction:raise FenceBlocked('Evidence marker requires the producer write transaction')
    assert_not_resolved(c,job_id)
    if 'recovery_evidence_state' in _columns(c):
        c.execute("UPDATE ai_compute_jobs SET recovery_evidence_state='observed' WHERE id=? AND recovery_evidence_state='absent'",(job_id,))


def _initialize(c):
    if 'worker_loss_resolutions' not in processes._tables(c):
        if c.execute('SELECT 1 FROM ai_compute_jobs WHERE operator_loss_id IS NOT NULL LIMIT 1').fetchone():
            raise FenceBlocked('Operator loss journal missing; cannot recreate approvals')
    c.execute('''CREATE TABLE IF NOT EXISTS worker_loss_resolutions(
      id TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),
      job_id TEXT NOT NULL UNIQUE REFERENCES ai_compute_jobs(id),request_id TEXT NOT NULL UNIQUE,
      record_json TEXT NOT NULL,sha256 TEXT NOT NULL)''')
    c.execute('''CREATE TRIGGER IF NOT EXISTS worker_loss_immutable_update BEFORE UPDATE ON worker_loss_resolutions
      BEGIN SELECT RAISE(ABORT,'Immutable operator loss approval'); END''')
    c.execute('''CREATE TRIGGER IF NOT EXISTS worker_loss_immutable_delete BEFORE DELETE ON worker_loss_resolutions
      WHEN mta_worker_loss_erasure(OLD.id)=0
      BEGIN SELECT RAISE(ABORT,'Immutable operator loss approval'); END''')


def _optional(c, table, query, job_id):
    if table not in processes._tables(c):return None
    row=c.execute(query,(job_id,)).fetchone()
    return dict(row) if row else None


def _snapshot(c, job_id):
    from .ai_arranger_runtime import _process_identity
    job=c.execute('SELECT * FROM ai_compute_jobs WHERE id=?',(job_id,)).fetchone()
    if job is None:raise ValueError('Unknown accounting job')
    job=dict(job)
    if (job.get('operator_loss_id') or job['status']!='running' or job.get('accounting_excluded')!=0
            or job.get('recovery_evidence_state')!='absent' or json.loads(job['usage_json'])!={}
            or job['resource_source']!='unmetered'):
        raise FenceBlocked('Existing evidence, legacy uncertainty or settled work requires original recovery')
    if not job.get('worker_scope_count'):raise FenceBlocked('Durable registered worker scopes required')
    for table,query in (('ai_verified_gpu_evidence','SELECT 1 FROM ai_verified_gpu_evidence WHERE job_id=?'),
                        ('ai_gpu_evidence_claims','SELECT 1 FROM ai_gpu_evidence_claims WHERE job_id=?'),
                        ('ai_trusted_estimate_evidence','SELECT 1 FROM ai_trusted_estimate_evidence WHERE job_id=?')):
        if table in processes._tables(c) and c.execute(query,(job_id,)).fetchone():
            raise FenceBlocked('Persisted metering evidence requires original recovery')
    processes.require_quiescent(c,job_id)
    scopes=[]
    for scope_id, in c.execute('SELECT id FROM worker_cgroup_scopes WHERE job_id=? ORDER BY id',(job_id,)):
        row,binding=processes._scope(c,scope_id)
        if binding.get('financial_loss_protocol')!=1:
            raise FenceBlocked('Original worker did not declare financial recovery coverage')
        if binding['host']!=processes._host():raise FenceBlocked('Original local host/boot/namespace required')
        current=_process_identity(binding['supervisor_pid'])
        if current=='' or current==binding['supervisor_identity']:
            raise FenceBlocked('Original supervisor must be proven dead before economic resolution')
        receipt=c.execute('SELECT sha256 FROM worker_cgroup_receipts WHERE scope_id=?',(scope_id,)).fetchone()
        scopes.append({'scope_id':scope_id,'binding_sha256':row['sha256'],'receipt_sha256':receipt[0]})
    claim=c.execute('SELECT * FROM regime_worker_claims WHERE operation_id=?',('job:ledger:'+job_id,)).fetchone()
    if claim is None or claim['state']!='running':raise FenceBlocked('Original running economic claim required')
    from .deferred_execution_owner import validate_receipt
    validate_receipt(c,job_id,claim['worker_id'],claim['claim_token'])
    from .service_regime import read_regime
    mirror=read_regime(auth.data_root()/'service-regime.json')
    if (mirror.regime.value,mirror.revision)!=(claim['regime'],claim['revision']):
        raise FenceBlocked('Original service regime mirror drift')
    contract=_optional(c,'resource_job_contracts','SELECT * FROM resource_job_contracts WHERE job_id=?',job_id)
    budget=_optional(c,'resource_job_budgets','SELECT * FROM resource_job_budgets WHERE job_id=?',job_id)
    if budget and (type(budget['budget_micro']) is not int or budget['budget_micro']<0):
        raise FenceBlocked('Original reservation limit is invalid')
    requirement=_optional(c,'ai_job_settlement_requirements','SELECT * FROM ai_job_settlement_requirements WHERE job_id=?',job_id)
    if requirement is None or (requirement['resource_contract_required'] and contract is None):
        raise FenceBlocked('Original accounting contract cannot be verified')
    if contract and (contract['settled'] or contract['charge_micro']):raise FenceBlocked('Existing settlement requires reconciliation')
    lease=_optional(c,'ai_gpu_slot_leases','SELECT * FROM ai_gpu_slot_leases WHERE job_id=?',job_id)
    if c.execute('SELECT 1 FROM ai_billing_periods WHERE user_id=? AND start_ts<? AND end_ts>? LIMIT 1',
                 (job['user_id'],int(time.time())+1,job['started_at'])).fetchone():
        raise FenceBlocked('Closed billing period cannot be rewritten')
    safe_claim={k:claim[k] for k in ('operation_id','worker_id','regime','revision','state','heartbeat_count')}
    safe_claim['token_sha256']=hashlib.sha256(claim['claim_token'].encode()).hexdigest()
    return {'job':job,'claim':safe_claim,'scopes':scopes,'contract':contract,'budget':budget,
            'requirement':requirement,'gpu_lease':lease,'policy':'operator_absorbs_unknown_no_reallocation_v1'}


def preview(c, job_id, actor):
    processes._admin(c,actor)
    snap=_snapshot(c,job_id)
    if snap['job']['user_id']==actor:raise FenceBlocked('Another administrator must review their own job')
    _,digest=processes._encode(snap)
    return {'job_id':job_id,'user_id':snap['job']['user_id'],'expected_sha256':digest,
            'customer_charge_micro':0,'unknown_consumption':True,'inference_replayed':False,
            'credit_reservation_limit_micro':snap['budget']['budget_micro'] if snap['budget'] else None,
            'gpu_lease_active':bool(snap['gpu_lease'] and snap['gpu_lease']['state']=='active'),
            'operator_assumes_loss':True,'reallocation_to_other_users':False}


def _public(record):
    return {k:record[k] for k in ('id','job_id','user_id','actor_id','created_at','reason','evidence_sha256',
        'customer_charge_micro','unknown_consumption','operator_assumes_loss','reallocation_to_other_users',
        'credit_reservation_limit_micro','gpu_lease_released','expected_sha256')}


def _verified(c,row):
    record=processes._decode(row['record_json'],row['sha256'])
    if processes._encode(record['snapshot'])[1]!=record['expected_sha256']:
        raise FenceBlocked('Original loss preview digest inconsistent')
    job=c.execute('SELECT * FROM ai_compute_jobs WHERE id=?',(row['job_id'],)).fetchone()
    if (record['id']!=row['id'] or record['job_id']!=row['job_id'] or record['user_id']!=row['user_id']
        or record['request']['request_id']!=row['request_id'] or record['request']['expected_sha256']!=record['expected_sha256']
        or job is None or job['user_id']!=row['user_id'] or job['operator_loss_id']!=row['id']
        or job['status']!='failed' or job['accounting_excluded']!=1 or job['recovery_evidence_state']!='operator_loss'
        or job['resource_source']!='unmetered' or json.loads(job['usage_json'])!={}
        or record['customer_charge_micro']!=0 or record['unknown_consumption'] is not True
        or record['operator_assumes_loss'] is not True or record['reallocation_to_other_users'] is not False):
        raise FenceBlocked('Operator loss approval or original ledger inconsistent')
    expected_job={**record['snapshot']['job'],'status':'failed','finished_at':record['created_at']//1_000_000_000,
                  'wall_ms':(record['created_at']//1_000_000_000-record['snapshot']['job']['started_at'])*1000,
                  'accounting_excluded':1,'operator_loss_id':record['id'],'recovery_evidence_state':'operator_loss'}
    if any(job[k]!=v for k,v in expected_job.items()):raise FenceBlocked('Original accounting job changed after loss approval')
    contract=_optional(c,'resource_job_contracts','SELECT * FROM resource_job_contracts WHERE job_id=?',row['job_id'])
    if contract and (contract['settled']!=1 or contract['charge_micro']!=0):raise FenceBlocked('Loss contract not settled consistently')
    state=c.execute('SELECT state FROM regime_worker_claims WHERE operation_id=?',('job:ledger:'+row['job_id'],)).fetchone()
    fence=c.execute('SELECT status FROM regime_fence_operations WHERE operation_id=?',('job:ledger:'+row['job_id'],)).fetchone()
    if state is None or state[0]!='finished' or fence is None or fence[0]!='closed':raise FenceBlocked('Loss claim/fence incomplete')
    processes.require_quiescent(c,row['job_id'])
    actual=[]
    for sid, in c.execute('SELECT id FROM worker_cgroup_scopes WHERE job_id=? ORDER BY id',(row['job_id'],)):
        s=c.execute('SELECT sha256 FROM worker_cgroup_scopes WHERE id=?',(sid,)).fetchone()
        r=c.execute('SELECT sha256 FROM worker_cgroup_receipts WHERE scope_id=?',(sid,)).fetchone()
        actual.append({'scope_id':sid,'binding_sha256':s[0],'receipt_sha256':r[0]})
    if actual!=record['snapshot']['scopes']:raise FenceBlocked('Loss quiescence history changed')
    lease=_optional(c,'ai_gpu_slot_leases','SELECT * FROM ai_gpu_slot_leases WHERE job_id=?',row['job_id'])
    if lease and lease['state']=='active':raise FenceBlocked('Loss GPU reservation remains active')
    budget=_optional(c,'resource_job_budgets','SELECT * FROM resource_job_budgets WHERE job_id=?',row['job_id'])
    if record['post']!={'contract':contract,'budget':budget,'gpu_lease':lease}:
        raise FenceBlocked('Approved financial reservation outcome changed')
    return record


def resolve(job_id,actor,body):
    required={'request_id','expected_sha256','reason','evidence_sha256','confirm_operator_loss','confirm_no_customer_charge','confirm_no_reallocation'}
    if not isinstance(body,dict) or set(body)!=required:raise ValueError('Exact operator loss fields required')
    if any(body[k] is not True for k in ('confirm_operator_loss','confirm_no_customer_charge','confirm_no_reallocation')):
        raise ValueError('Explicit operator loss/no-charge/no-reallocation confirmations required')
    if not isinstance(body['request_id'],str) or not re.fullmatch(r'[A-Za-z0-9_-]{16,100}',body['request_id']):raise ValueError('Invalid request identifier')
    if not isinstance(body['reason'],str) or not 20<=len(body['reason'].strip())<=2000:raise ValueError('Documented reason required')
    for key in ('expected_sha256','evidence_sha256'):
        if not isinstance(body[key],str) or not re.fullmatch(r'[a-f0-9]{64}',body[key]):raise ValueError('SHA-256 evidence and preview required')
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE')
        processes._admin(c,actor)
        _initialize(c)
        old=c.execute('SELECT * FROM worker_loss_resolutions WHERE job_id=? OR request_id=?',(job_id,body['request_id'])).fetchone()
        if old:
            record=_verified(c,old)
            if record['job_id']!=job_id or record['actor_id']!=actor or record['request']!=body:
                raise FenceBlocked('Conflicting operator loss approval replay')
            return _public(record)
        plan=preview(c,job_id,actor)
        if plan['expected_sha256']!=body['expected_sha256']:raise FenceBlocked('Loss preview is stale; review current reservations again')
        snap=_snapshot(c,job_id)
        now=time.time_ns();end=now//1_000_000_000
        if end<snap['job']['started_at']:raise FenceBlocked('Accounting clock precedes admission')
        claim=c.execute('SELECT worker_id,claim_token FROM regime_worker_claims WHERE operation_id=?',('job:ledger:'+job_id,)).fetchone()
        record={**plan,'id':uuid.uuid4().hex,'actor_id':actor,'created_at':now,'reason':body['reason'],
                'evidence_sha256':body['evidence_sha256'],'request':body,'snapshot':snap,
                'gpu_lease_released':bool(snap['gpu_lease'] and snap['gpu_lease']['state']=='active')}
        c.execute("UPDATE ai_compute_jobs SET status='failed',finished_at=?,wall_ms=?,accounting_excluded=1,operator_loss_id=?,recovery_evidence_state='operator_loss' WHERE id=? AND status='running'",
                  (end,(end-snap['job']['started_at'])*1000,record['id'],job_id))
        from .resource_accounts import settle
        settle(c,job_id,{})  # Agreed customer charge zero; physical usage stays unknown.
        if record['gpu_lease_released']:
            if now//1_000_000<snap['gpu_lease']['acquired_ms']:raise FenceBlocked('GPU reservation clock is inconsistent')
            c.execute("UPDATE ai_gpu_slot_leases SET state='aborted',released_ms=? WHERE job_id=? AND state='active'",(now//1_000_000,job_id))
        from .regime_worker_claims import finish
        finish(c,'job:ledger:'+job_id,worker_id=claim['worker_id'],token=claim['claim_token'])
        from .regime_job_fence import settle_metered_job
        settle_metered_job(c,job_id)
        record['post']={'contract':_optional(c,'resource_job_contracts','SELECT * FROM resource_job_contracts WHERE job_id=?',job_id),
                        'budget':_optional(c,'resource_job_budgets','SELECT * FROM resource_job_budgets WHERE job_id=?',job_id),
                        'gpu_lease':_optional(c,'ai_gpu_slot_leases','SELECT * FROM ai_gpu_slot_leases WHERE job_id=?',job_id)}
        raw,digest=processes._encode(record)
        c.execute('INSERT INTO worker_loss_resolutions VALUES(?,?,?,?,?,?)',(record['id'],plan['user_id'],job_id,body['request_id'],raw,digest))
        _verified(c,c.execute('SELECT * FROM worker_loss_resolutions WHERE job_id=?',(job_id,)).fetchone())
        return _public(record)


def history(c,uid=None):
    tables=processes._tables(c)
    if 'worker_loss_resolutions' not in tables:
        if 'operator_loss_id' in _columns(c) and c.execute('SELECT 1 FROM ai_compute_jobs WHERE operator_loss_id IS NOT NULL LIMIT 1').fetchone():
            raise FenceBlocked('Operator loss journal unavailable')
        return []
    if c.execute('SELECT 1 FROM ai_compute_jobs j LEFT JOIN worker_loss_resolutions r ON r.id=j.operator_loss_id WHERE j.operator_loss_id IS NOT NULL AND r.id IS NULL LIMIT 1').fetchone():
        raise FenceBlocked('Operator loss receipt missing')
    rows=c.execute('SELECT * FROM worker_loss_resolutions ORDER BY rowid DESC').fetchall()
    result=[]
    for row in rows:
        item=_verified(c,row)
        if uid is None or item['user_id']==uid:result.append(_public(item))
    return result


def recover_frozen(job_id,actor,publish):
    """Retry the existing publication/accounting saga; never infer again."""
    from . import ai_arranger_runtime as queue, ai_metering_bridge as bridge
    from . import ai_publish_outbox as publication, ai_finalization
    with auth.db() as c:
        processes._admin(c,actor)
        assert_not_resolved(c,job_id)
        job=c.execute('SELECT user_id,kind,queue_job_id FROM ai_compute_jobs WHERE id=?',(job_id,)).fetchone()
        if job is None or not job['queue_job_id']:raise FenceBlocked('Original durable inference binding required')
        processes.require_quiescent(c,job_id)
    if not (queue._ROOT/'jobs.sqlite3').is_file() or not (queue._ROOT/'publication'/'outbox.sqlite3').is_file():
        raise FenceBlocked('Original queue/publication history unavailable; cannot recreate evidence')
    qid=job['queue_job_id']
    if bridge._identity(qid)!=(job['user_id'],job['kind']):raise FenceBlocked('Original inference/account binding mismatch')
    frozen=publication.status(qid)
    with queue._db() as c:scheduled=c.execute('SELECT project_id FROM jobs WHERE job_id=?',(qid,)).fetchone()
    if frozen is None or scheduled is None or frozen['project_id']!=scheduled[0]:
        raise FenceBlocked('Original staged publication/project binding unavailable')
    publication.recover(publish,job_id=qid)
    ready=ai_finalization.reconcile(qid)
    return {'job_id':job_id,'inference_id':qid,'original_result_recovered':bool(ready),'inference_replayed':False}


def period_losses(c,start,end):
    rows=history(c)
    return [{'id':r['id'],'job_id':r['job_id'],'unknown_consumption':True}
            for r in rows if c.execute('SELECT 1 FROM ai_compute_jobs WHERE id=? AND started_at<? AND finished_at>=?',(r['job_id'],end,start)).fetchone()]


def audit(c):
    try:
        rows=history(c)
        return {'verified':True,'approved_operator_losses':len(rows),'customer_charge_micro':0,
                'unknown_consumption_retained':True,'transition_enabled':False}
    except (FenceBlocked,sqlite3.DatabaseError,ValueError,KeyError,TypeError):
        return {'verified':False,'approved_operator_losses':None,'customer_charge_micro':None,
                'unknown_consumption_retained':True,'transition_enabled':False}


def authorize_account_erasure(c,uid,actor):
    if 'worker_loss_resolutions' not in processes._tables(c):return
    if not c.in_transaction:raise FenceBlocked('Loss erasure requires a write transaction')
    ids={r[0] for r in c.execute('SELECT id FROM worker_loss_resolutions WHERE user_id=?',(uid,))}
    if not ids:return
    processes._admin(c,actor)
    owner=c.execute('SELECT role,active FROM users WHERE id=?',(uid,)).fetchone()
    life=c.execute('SELECT state FROM account_lifecycle WHERE user_id=?',(uid,)).fetchone()
    if owner is None or owner[0]=='admin' or owner[1] or life is None or life[0] not in ('deleted','expired','erasing'):
        raise FenceBlocked('Approved retired-account erasure required')
    c.create_function('mta_worker_loss_erasure',1,lambda key:int(key in ids))
