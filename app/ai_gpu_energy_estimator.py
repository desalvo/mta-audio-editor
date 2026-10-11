"""Auditable calibrated *estimates* of per-job GPU energy (not hardware joulemeter).

Only job-scoped measured engine time is accepted. Host-wide GPU utilization
is never an attribution source. Exclusive device allocation must be verified
outside this module; shared-device estimates are diagnostic only.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class EnergyCalibration:
    gpu_id: str
    idle_watts: float
    full_load_watts: float
    method: str = 'calibrated-full-load-v1'

    def validate(self) -> None:
        if not self.gpu_id or len(self.gpu_id) > 160:
            raise ValueError('GPU identity required')
        if self.method != 'calibrated-full-load-v1':
            raise ValueError('Unknown calibration method')
        if not all(math.isfinite(v) and v >= 0 for v in (self.idle_watts, self.full_load_watts)):
            raise ValueError('Power calibration must be finite and nonnegative')
        if self.full_load_watts <= self.idle_watts:
            raise ValueError('Full-load power must exceed idle power')


def estimate_job_energy(
    calibration: EnergyCalibration, *, gpu_engine_seconds: float,
    job_wall_seconds: float, exclusive_gpu: bool,
    complete_lifecycle: bool, baseline_policy: str = 'incremental',
) -> dict:
    """Estimate energy from job-scoped engine time; never host utilization.

    GPU engines can overlap: caller supplies a *non-overlapping* busy-time
    equivalent, not a raw sum of concurrent DRM engine counters. If the
    caller cannot establish it, complete_lifecycle must be False.
    """
    calibration.validate()
    if baseline_policy not in ('incremental', 'total'):
        raise ValueError('Unknown idle-power policy')
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and
               math.isfinite(v) and v >= 0 for v in (gpu_engine_seconds, job_wall_seconds)):
        raise ValueError('Durations must be finite nonnegative values')
    if gpu_engine_seconds > job_wall_seconds + 1e-6:
        raise ValueError('Overlapping engine clocks cannot be added as GPU busy time')
    result = {
        'gpu_id': calibration.gpu_id,
        'calibration': asdict(calibration),
        'gpu_engine_seconds': float(gpu_engine_seconds),
        'job_wall_seconds': float(job_wall_seconds),
        'exclusive_gpu': bool(exclusive_gpu),
        'complete_lifecycle': bool(complete_lifecycle),
        'baseline_policy': baseline_policy,
        'unit': 'joule',
        'kind': 'estimated_not_measured',
        'billing_eligible': False,
        'reason': '',
        'estimated_energy_joules': None,
    }
    if not exclusive_gpu:
        result['reason'] = 'GPU shared with other processes: energy not attributable'
        return result
    if not complete_lifecycle:
        result['reason'] = 'GPU process lifecycle or engine counters incomplete'
        return result
    incremental = (calibration.full_load_watts - calibration.idle_watts) * gpu_engine_seconds
    result['estimated_energy_joules'] = (
        incremental + calibration.idle_watts * job_wall_seconds
        if baseline_policy == 'total' else incremental
    )
    result['reason'] = 'Calibrated estimate, not measured per-job GPU energy'
    return result


def store_calibration(profile: EnergyCalibration) -> None:
    """Admin-controlled calibration retained separately from invoiced usage."""
    import json
    import time
    from .auth import db
    profile.validate()
    with db() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS ai_gpu_energy_calibrations (
            gpu_id TEXT PRIMARY KEY, profile_json TEXT NOT NULL, updated_at INTEGER NOT NULL)''')
        conn.execute('INSERT INTO ai_gpu_energy_calibrations(gpu_id,profile_json,updated_at) VALUES(?,?,?) '
                     'ON CONFLICT(gpu_id) DO UPDATE SET profile_json=excluded.profile_json, '
                     'updated_at=excluded.updated_at',
                     (profile.gpu_id, json.dumps(asdict(profile), sort_keys=True), int(time.time())))


def calibrations() -> list[dict]:
    import json
    from .auth import db
    with db() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS ai_gpu_energy_calibrations (
            gpu_id TEXT PRIMARY KEY, profile_json TEXT NOT NULL, updated_at INTEGER NOT NULL)''')
        return [dict(json.loads(row[0]), updated_at=row[1]) for row in conn.execute(
            'SELECT profile_json,updated_at FROM ai_gpu_energy_calibrations ORDER BY gpu_id')]
