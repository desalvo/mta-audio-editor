"""Validate job-scoped HIP event telemetry as *diagnostic* evidence.

HIP elapsed time is elapsed stream time, not exclusive device busy time.
Never convert it into billable gpu_seconds without separate attestation and
concurrency/exclusivity certification. The producer is not a trusted gpu-agent.
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class HIPEventSample:
    job_id: str
    device_id: int
    process_pid: int
    elapsed_ms: float
    event_pairs: int
    wall_seconds: float
    synchronized: bool


def parse_hip_event_sample(payload: str | dict, *, expected_job_id: str) -> dict:
    """Parse a bounded, nonbillable report from an instrumented HIP worker.

    A worker-controlled record is diagnostic only, even if internally valid.
    The caller must identify the worker/job using its own trusted context.
    """
    if isinstance(payload, str):
        if len(payload) > 8192:
            raise ValueError('HIP event report too large')
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError('Invalid HIP event JSON') from exc
    if not isinstance(payload, dict) or set(payload) != {
        'job_id', 'device_id', 'process_pid', 'elapsed_ms',
        'event_pairs', 'wall_seconds', 'synchronized',
    }:
        raise ValueError('Invalid HIP event report fields')
    if not isinstance(expected_job_id, str) or not expected_job_id:
        raise ValueError('Expected job identity required')
    if payload['job_id'] != expected_job_id:
        raise ValueError('HIP event job identity mismatch')
    for key, lower in (('device_id', 0), ('process_pid', 1), ('event_pairs', 1)):
        value = payload[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < lower:
            raise ValueError(f'Invalid {key}')
    for key in ('elapsed_ms', 'wall_seconds'):
        value = payload[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError(f'Invalid {key}')
    if payload['synchronized'] is not True:
        raise ValueError('HIP events must be synchronized')
    sample = HIPEventSample(**payload)
    result = asdict(sample)
    result.update({
        'collector': 'hip-events-v1',
        'gpu_event_elapsed_seconds': sample.elapsed_ms / 1000.0,
        'billing_eligible': False,
        'resource_source': 'diagnostic-hip-events',
        'reason': 'Stream elapsed time is not certified exclusive GPU busy time',
    })
    return result
