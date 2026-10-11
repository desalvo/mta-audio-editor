"""Bounded in-memory AI job planning queue; no fake inference, no project mutations.

Jobs are process-local: intended for preview control and testing, not a distributed queue.
A production GPU worker must be attached before any job can enter `running`.
"""
from __future__ import annotations
from datetime import datetime, timezone
from copy import deepcopy
from threading import RLock
from uuid import uuid4

MAX_JOBS = 128
TERMINAL = frozenset({'cancelled', 'completed', 'failed'})


class AIJobQueue:
    def __init__(self):
        self._lock = RLock()
        self._jobs: dict[str, dict] = {}

    def submit(self, project_id: str, owner_id: str, operation: str, plan: dict) -> dict:
        if operation not in ('remix', 'rearrange'):
            raise ValueError('unsupported AI operation')
        with self._lock:
            if not isinstance(plan, dict):
                raise ValueError('AI plan must be a mapping')
            if len(self._jobs) >= MAX_JOBS:
                # Safely evict only terminal jobs; never evict active work.
                older = next((key for key, val in self._jobs.items() if val['status'] in TERMINAL), None)
                if older is None:
                    raise ValueError('AI planning queue at capacity')
                del self._jobs[older]
            key = uuid4().hex
            self._jobs[key] = {
                'id': key, 'project_id': project_id, 'owner_id': owner_id,
                'operation': operation, 'status': 'planned',
                'generation_available': False,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'plan': deepcopy(plan),
                'message': 'Plan ready. No verified inference worker configured.',
            }
            return deepcopy(self._jobs[key])

    def get(self, job_id: str, project_id: str, owner_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return deepcopy(job) if job and job['project_id'] == project_id and job['owner_id'] == owner_id else None

    def cancel(self, job_id: str, project_id: str, owner_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job['project_id'] != project_id or job['owner_id'] != owner_id:
                return None
            if job['status'] == 'planned':
                job['status'] = 'cancelled'
                job['message'] = 'Plan cancelled before inference.'
            return deepcopy(job)


ai_jobs = AIJobQueue()
