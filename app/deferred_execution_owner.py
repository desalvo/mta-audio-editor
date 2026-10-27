"""Owner receipts for a durable inference's deferred publication/billing saga.

A restarted process may deliver a frozen settlement receipt, but may not infer
again using that receipt. Claim ownership is never transferred automatically.
All records live in the existing authoritative local ledger; this does not
claim distributed multi-host coordination.
"""

from .service_admission import worker_thread
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass,field
import os
import secrets
import socket
import threading

from .regime_operation_fence import FenceBlocked

_CURRENT=ContextVar('mta_deferred_execution_owner',default=None)
HEARTBEAT_INTERVAL=2


@dataclass(frozen=True)
class Owner:
    inference_id:str
    ledger_id:str
    worker_id:str
    claim_token:str
    lost:threading.Event=field(default_factory=threading.Event,compare=False,repr=False)

    def credentials(self):return {'worker_id':self.worker_id,'claim_token':self.claim_token}

    def receipt(self):return {'inference_id':self.inference_id,'ledger_id':self.ledger_id,**self.credentials()}


def validate_receipt(connection,ledger_id,worker_id,claim_token,*,allow_finished=False):
    from .worker_loss_resolution import assert_not_resolved
    assert_not_resolved(connection,ledger_id)
    from .regime_worker_claims import verify_owner
    verify_owner(connection,'job:ledger:'+ledger_id,worker_id=worker_id,token=claim_token,
                 allow_finished=allow_finished)
    row=connection.execute('''SELECT c.worker_id,c.claim_token,c.state,c.regime,c.revision,
      f.regime,f.revision,f.status,f.kind,j.status,s.regime,s.revision FROM regime_worker_claims c
      JOIN regime_fence_operations f ON f.operation_id=c.operation_id
      JOIN ai_compute_jobs j ON j.id=? CROSS JOIN regime_fence_state s
      WHERE c.operation_id=? AND s.singleton=1''',(ledger_id,'job:ledger:'+ledger_id)).fetchone()
    if (row is None or tuple(row[:2])!=(worker_id,claim_token) or tuple(row[3:5])!=tuple(row[5:7])
        or (tuple(row[2:3])+tuple(row[7:8])) not in (('running','open'),('finished','closed'))
        or row[8]!='job' or (row[2]=='running' and (row[9]!='running' or tuple(row[3:5])!=tuple(row[10:12])))
        or (row[2]=='finished' and (not allow_finished or row[9] not in ('done','failed','cancelled','completed','success','succeeded','canceled','refunded')))):
        raise FenceBlocked('Deferred execution ownership is missing, changed or no longer active')


def credentials_for(ledger_id):
    owner=_CURRENT.get()
    if owner is None:raise FenceBlocked('Deferred worker requires its active execution owner')
    if owner.lost.is_set():raise FenceBlocked('Deferred execution heartbeat was lost')
    if owner.ledger_id!=ledger_id:raise FenceBlocked('Deferred worker ledger ownership mismatch')
    return owner.credentials()


def cgroup_receipt():
    """Bind legacy project-worker cgroups to the current economic owner too."""
    owner=_CURRENT.get()
    if owner is None:return None
    receipt_for(owner.inference_id)
    return {'job_id':owner.ledger_id,**owner.credentials()}


def receipt_for(inference_id):
    owner=_CURRENT.get()
    if owner is None:
        # An existing claimed inference must never acquire unowned evidence.
        from . import auth
        if auth.db_path().is_file():
            from . import ai_billing
            with ai_billing.db() as c:
                tables={row[0] for row in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if {'regime_worker_claims','ai_compute_jobs'}<=tables:
                    claimed=c.execute("SELECT 1 FROM regime_worker_claims r JOIN ai_compute_jobs j ON r.operation_id='job:ledger:'||j.id WHERE j.queue_job_id=?",(inference_id,)).fetchone()
                    if claimed:raise FenceBlocked('Claimed inference requires its execution owner before staging or metering')
        return None
    if owner.inference_id!=inference_id:raise FenceBlocked('Metering owner belongs to another inference')
    if owner.lost.is_set():raise FenceBlocked('Deferred execution heartbeat was lost')
    from . import ai_billing
    with ai_billing.db() as c:validate_receipt(c,owner.ledger_id,owner.worker_id,owner.claim_token)
    return owner.receipt()


@contextmanager
def execution_scope(inference_id,cancel_event):
    """Claim before execution and heartbeat until publication/settlement handoff."""
    from . import ai_arranger_runtime as queue,ai_billing,ai_metering_bridge
    owner=None
    if queue.durable_audio_job(inference_id):
        payload=queue.read_payload(inference_id)
        if isinstance(payload,dict) and payload.get('actor_user_id') is not None:
            uid,operation=ai_metering_bridge._identity(inference_id)
            ledger=ai_billing.existing_inference_ledger_job(inference_id,uid,operation)
            if ledger is not None:
                with queue._db() as c:
                    runner=c.execute('SELECT state,runner_pid,runner_identity FROM jobs WHERE job_id=?',(inference_id,)).fetchone()
                identity=queue._process_identity(os.getpid())
                if not identity or runner is None or tuple(runner)!=('running',os.getpid(),identity):
                    raise FenceBlocked('Only the current durable scheduler owner may execute')
                owner=Owner(inference_id,ledger,'deferred:'+socket.gethostname()+':'+str(os.getpid()),secrets.token_hex(32))
                from .regime_worker_claims import claim
                with ai_billing.db() as c:
                    c.execute('BEGIN IMMEDIATE')
                    claim(c,ledger,worker_id=owner.worker_id,token=owner.claim_token)
    token=_CURRENT.set(owner);finished=threading.Event();errors=[]
    def pulse():
        from .regime_worker_claims import heartbeat
        while not finished.wait(HEARTBEAT_INTERVAL):
            try:
                with ai_billing.db() as c:
                    c.execute('BEGIN IMMEDIATE')
                    row=c.execute('SELECT state FROM regime_worker_claims WHERE operation_id=?',('job:ledger:'+owner.ledger_id,)).fetchone()
                    if row is not None and row[0]=='finished':
                        validate_receipt(c,owner.ledger_id,owner.worker_id,owner.claim_token,allow_finished=True)
                        return
                    heartbeat(c,'job:ledger:'+owner.ledger_id,worker_id=owner.worker_id,token=owner.claim_token)
            except Exception as exc:
                owner.lost.set();errors.append(exc);cancel_event.set();return
    thread=worker_thread(target=pulse,daemon=True,name='mta-owner-heartbeat') if owner else None
    if thread:thread.start()
    try:
        yield owner
        if errors:raise FenceBlocked('Execution owner heartbeat failed; external result remains uncertain') from errors[0]
    finally:
        finished.set()
        if thread:thread.join(5)
        _CURRENT.reset(token)


def validate_persisted(receipt,inference_id):
    if not isinstance(receipt,dict) or set(receipt)!={'inference_id','ledger_id','worker_id','claim_token'} or receipt['inference_id']!=inference_id:
        raise FenceBlocked('Invalid persisted execution owner receipt')
    from . import ai_billing,ai_metering_bridge
    uid,kind=ai_metering_bridge._identity(inference_id)
    if ai_billing.existing_inference_ledger_job(inference_id,uid,kind)!=receipt['ledger_id']:
        raise FenceBlocked('Persisted execution owner belongs to another ledger')
    with ai_billing.db() as c:
        validate_receipt(c,receipt['ledger_id'],receipt['worker_id'],receipt['claim_token'],allow_finished=True)
