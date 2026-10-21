"""One admission path for authenticated inference, including nested web jobs."""
from contextvars import ContextVar
import threading
import uuid

current_job=ContextVar('mta_global_ai_job',default=None)
current_cancel=ContextVar('mta_global_ai_cancel',default=None)


def execute(user_id,kind,call,*,cancel_check=None,license_decision=None):
    from . import ai_arranger_runtime as queue
    if current_job.get() is not None:
        event=current_cancel.get()
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
