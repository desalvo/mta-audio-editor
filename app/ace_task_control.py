"""Authenticated, bounded ACE task budgets and cooperative PyTorch cancellation.

No process-wide kill, unsafe thread injection, or billing authority.
"""
from __future__ import annotations
from contextlib import contextmanager
from functools import wraps
import re
import sys
import threading
import time

MAX_BUDGET = 14400
SERVICE_GUARD_SECONDS = MAX_BUDGET + 120


class TaskStopped(RuntimeError):
    pass


class TaskControl:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.lock = threading.RLock()
        self.tasks = {}

    def _record(self, task):
        if not isinstance(task, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', task):
            raise ValueError('Invalid ACE task ID')
        with self.lock:
            if task not in self.tasks:
                # Never evict an active inference to admit arbitrary requests.
                for key, value in list(self.tasks.items()):
                    if not value.get('active_services') and value['state'] not in ('running', 'pending') and self.clock() - value['created'] > SERVICE_GUARD_SECONDS:
                        del self.tasks[key]
                if len(self.tasks) >= 512:
                    for key, value in list(self.tasks.items()):
                        if not value.get('active_services') and value['state'] in ('completed', 'failed', 'cancelled'):
                            del self.tasks[key]
                            break
                if len(self.tasks) >= 512:
                    raise ValueError('ACE task control capacity reached')
                self.tasks[task] = {'created': self.clock(), 'started': None,
                    'budget': MAX_BUDGET, 'configured': False, 'cancel': False, 'state': 'pending'}
            return self.tasks[task]

    def configure(self, task, *, timeout_seconds=None, cancel=False):
        with self.lock:
            row = self._record(task)
            if timeout_seconds is not None:
                if type(timeout_seconds) is not int or not 60 <= timeout_seconds <= MAX_BUDGET:
                    raise ValueError('ACE budget must be 60–14400 seconds')
                if row['configured'] and row['budget'] != timeout_seconds:
                    raise ValueError('ACE task budget is immutable')
                row['budget'], row['configured'] = timeout_seconds, True
            if cancel and row['state'] not in ('completed', 'failed', 'cancelled'):
                row['cancel'] = True
            return {'task_id': task, 'state': row['state'], 'cancel_requested': row['cancel'],
                    'timeout_seconds': row['budget'], 'billing_eligible': False}

    def check(self, task):
        with self.lock:
            row = self._record(task)
            if row['cancel']:
                raise TaskStopped('MTA ACE task cancelled')
            if row['started'] is not None and self.clock() - row['started'] >= row['budget']:
                raise TaskStopped('MTA ACE task processing timeout')

    @contextmanager
    def checkpoints(self, task):
        """Checks only this inference thread, including the upstream GPU child."""
        owner = threading.get_ident()
        torch = sys.modules.get('torch')
        register = getattr(getattr(getattr(getattr(torch, 'nn', None), 'modules', None), 'module', None),
                           'register_module_forward_pre_hook', None)
        compiling = getattr(getattr(torch, 'compiler', None), 'is_compiling', lambda: False)
        def checkpoint(*args):
            if threading.get_ident() == owner and not compiling():
                self.check(task)
        hook = register(checkpoint) if callable(register) else None
        try:
            self.check(task)
            yield
            self.check(task)
        finally:
            if hook is not None:
                hook.remove()

    def wrap(self, target, profiler):
        @wraps(target)
        def execute(*args, **kwargs):
            task = kwargs['job_id']
            with self.lock:
                row = self._record(task)
                row['started'], row['state'] = self.clock(), 'running'
            handler = kwargs.get('selected_handler')
            service = getattr(handler, 'service_generate', None)
            # Upstream actually runs diffusion in a service-generate thread.
            # Start the profiler there so live captures use their owner thread.
            had_override = handler is not None and 'service_generate' in getattr(handler, '__dict__', {})
            previous = getattr(handler, '__dict__', {}).get('service_generate')
            if callable(service):
                def guarded_service(*a, **kw):
                    with self.lock:
                        row['active_services'] = row.get('active_services', 0) + 1
                    def infer(*, job_id):
                        with self.checkpoints(job_id):
                            return service(*a, **kw)
                    try:
                        return profiler.wrap(infer)(job_id=task)
                    finally:
                        with self.lock:
                            row['active_services'] -= 1
                handler.service_generate = guarded_service
            try:
                with self.checkpoints(task):
                    result = target(*args, **kwargs) if callable(service) else profiler.wrap(target)(*args, **kwargs)
                with self.lock:
                    row['state'] = 'completed'
                return result
            except BaseException:
                with self.lock:
                    row['state'] = 'cancelled' if row['cancel'] else 'failed'
                    row['cancel'] = True
                raise
            finally:
                if callable(service):
                    if had_override:
                        handler.service_generate = previous
                    else:
                        del handler.service_generate
        return execute
