"""One admission path for authenticated inference, including nested web jobs."""
from contextvars import ContextVar
import threading
import uuid
import os
import sys

current_job=ContextVar('mta_global_ai_job',default=None)
current_cancel=ContextVar('mta_global_ai_cancel',default=None)


def active_owner(expected_user_id=None):
    """Recheck the durable owner before reusing a scheduler execution context.

    Context variables are routing hints, never authority to attach a new worker
    to an absent, terminal, foreign-owner or different supervisor's queue row.
    This is scheduler identity, not proof of external worker quiescence.
    """
    from . import ai_arranger_runtime as queue
    job_id=current_job.get()
    if job_id is None:
        raise ValueError('Authenticated active global AI job required')
    queue._validate_job_id(job_id)
    with queue._db() as c:
        row=c.execute('''SELECT actor_user_id,state,runner_pid,runner_identity,cancel_requested
            FROM jobs WHERE job_id=?''',(job_id,)).fetchone()
    identity=queue._process_identity(os.getpid())
    if (row is None or type(row[0]) is not int or row[0]<=0 or row[1]!='running'
            or row[2]!=os.getpid() or row[3]!=identity
            or (sys.platform in ('linux','win32') and not identity)):
        raise ValueError('Authenticated active global AI job required')
    if expected_user_id is not None and (type(expected_user_id) is not int or expected_user_id!=row[0]):
        raise ValueError('AI execution owner mismatch')
    if row[4] or (current_cancel.get() is not None and current_cancel.get().is_set()):
        raise RuntimeError('AI job cancelled before dispatch')
    return row[0]


def execute(user_id,kind,call,*,cancel_check=None,license_decision=None):
    from . import ai_arranger_runtime as queue
    if type(user_id) is not int or user_id<=0:
        raise ValueError('Authenticated AI execution owner required')
    if current_job.get() is not None:
        active_owner(user_id)
        event=current_cancel.get()
        if cancel_check and cancel_check():
            raise RuntimeError('AI job cancelled before dispatch')
        return call(lambda:bool(event and event.is_set()) or bool(cancel_check and cancel_check()))
    done=threading.Event();result={};jid=uuid.uuid4().hex
    def run(progress,stop):
        def cancelled():return stop.is_set() or bool(cancel_check and cancel_check())
        try:
            if cancelled():raise RuntimeError('AI job cancelled before dispatch')
            result['value']=call(cancelled)
        except BaseException as exc:
            result['error']=exc
            raise
        finally:done.set()
    from .model_license_policy import admission
    with admission(license_decision):
        queue.start('remote-user-'+str(user_id),'worker:'+kind,run,job_id=jid,cancellable=True,
            payload={'schema_version':1,'actor_user_id':user_id,'kind':kind,'remote_inference':True})
    try:
        while True:
            state=queue.get(jid)
            if state and state['state'] in ('completed','cancelled','failed','interrupted'):
                if 'error' in result:raise result['error']
                if state['state']!='completed':raise RuntimeError('AI job '+state['state'])
                return result['value']
            if not state:raise RuntimeError('AI job unavailable')
            if state['state']=='queued' and cancel_check and cancel_check():queue.cancel(jid)
            # Wait for the terminal queue transaction, not just inference return.
            threading.Event().wait(.05)
    except BaseException:
        try:queue.cancel(jid)
        except ValueError:pass
        raise
