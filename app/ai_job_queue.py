"""Bounded in-memory AI job planning queue; no fake inference, no project mutations.

Jobs are process-local: intended for preview control and testing, not a distributed queue.
A production GPU worker must be attached before any job can enter `running`.
"""
from __future__ import annotations
from datetime import datetime, timezone
from copy import deepcopy
import json
import math
from threading import RLock
from uuid import uuid4

MAX_JOBS = 128
MAX_PLAN_BYTES = 1024 * 1024
MAX_PLAN_DEPTH = 32
TERMINAL = frozenset({'cancelled', 'completed', 'failed'})


def _safe_plan(plan: dict) -> dict:
    """Accept bounded JSON-only plans; reject non-finite floats and cyclic objects.

    The planning API never runs inference, but it must not keep arbitrary mutable
    Python objects or unbounded payloads in a process-wide queue.
    """
    if not isinstance(plan, dict):
        raise ValueError('AI plan must be a mapping')
    seen = set()
    def validate(value, depth):
        if depth > MAX_PLAN_DEPTH:
            raise ValueError('AI plan nesting exceeds limit')
        if value is None or isinstance(value, (str, bool, int)):
            return
        if isinstance(value, float):
            if not math.isfinite(value):
                raise ValueError('AI plan includes non-finite numbers')
            return
        if isinstance(value, (dict, list)):
            identity = id(value)
            if identity in seen:
                raise ValueError('AI plan contains a cycle or repeated container')
            seen.add(identity)
            if isinstance(value, dict):
                for key, item in value.items():
                    if not isinstance(key, str):
                        raise ValueError('AI plan keys must be strings')
                    validate(item, depth + 1)
            else:
                for item in value:
                    validate(item, depth + 1)
            seen.remove(identity)
            return
        raise ValueError('AI plan contains an unsupported value')
    validate(plan, 0)
    try:
        serialized = json.dumps(plan, allow_nan=False, ensure_ascii=False, separators=(',', ':'))
        if len(serialized.encode('utf-8')) > MAX_PLAN_BYTES:
            raise ValueError('AI plan exceeds size limit')
        return json.loads(serialized)
    except (OverflowError, RecursionError, UnicodeError, TypeError) as exc:
        raise ValueError('AI plan cannot be serialized safely') from exc


class AIJobQueue:
    def __init__(self):
        self._lock = RLock()
        self._jobs: dict[str, dict] = {}

    def submit(self, project_id: str, owner_id: str, operation: str, plan: dict) -> dict:
        if operation not in ('remix', 'rearrange'):
            raise ValueError('unsupported AI operation')
        if not isinstance(project_id, str) or not project_id.strip():
            raise ValueError('project identifier is required')
        if not isinstance(owner_id, str) or not owner_id.strip():
            raise ValueError('owner identifier is required')
        verified_plan = _safe_plan(plan)
        with self._lock:
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
                'plan': verified_plan,
                'message': 'Plan ready. No verified inference worker configured.',
            }
            return deepcopy(self._jobs[key])

    def get(self, job_id: str, project_id: str, owner_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return deepcopy(job) if job and job['project_id'] == project_id and job['owner_id'] == owner_id else None

    def list(self, project_id: str, owner_id: str, *, limit: int = 20,
             offset: int = 0, status: str | None = None) -> dict:
        """Read-only, owner-scoped planning history with bounded pagination.

        Planning jobs are deliberately process-local. This method cannot imply
        durable inference status or enumerate another user's plans.
        """
        if not isinstance(project_id, str) or not project_id.strip():
            raise ValueError('project identifier is required')
        if not isinstance(owner_id, str) or not owner_id.strip():
            raise ValueError('owner identifier is required')
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('limit must be between 1 and 100')
        if type(offset) is not int or not 0 <= offset <= MAX_JOBS:
            raise ValueError('invalid pagination offset')
        if status is not None and status not in ('planned', 'cancelled', 'completed', 'failed'):
            raise ValueError('invalid status filter')
        with self._lock:
            matching = [job for job in self._jobs.values()
                        if job['project_id'] == project_id and job['owner_id'] == owner_id
                        and (status is None or job['status'] == status)]
            return {'items': deepcopy(matching[offset:offset + limit]),
                    'total': len(matching), 'limit': limit, 'offset': offset,
                    'durable': False, 'generation_available': False}

    def cancel(self, job_id: str, project_id: str, owner_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job['project_id'] != project_id or job['owner_id'] != owner_id:
                return None
            if job['status'] == 'planned':
                job['status'] = 'cancelled'
                job['message'] = 'Plan cancelled before inference.'
                job['cancelled_at'] = datetime.now(timezone.utc).isoformat()
            return deepcopy(job)


def create_planning_queue():
    """Opt in to a durable planning journal; never execute or bill these plans."""
    import os
    path = os.getenv('MTA_AI_PLANNING_DB', '').strip()
    if path:
        from .ai_planning_sqlite import SQLitePlanningQueue
        return SQLitePlanningQueue(path)
    return AIJobQueue()


ai_jobs = create_planning_queue()
