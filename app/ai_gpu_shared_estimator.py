"""Conservative, non-billable equivalent GPU capacity allocation.

A trusted scheduler must supply wall-clock windows and externally observed
whole-device utilization. HIP elapsed times are *weights*, not occupancy or
exclusive GPU time. Missing/untrusted observations never imply full usage.
"""
from __future__ import annotations

import math
from collections import defaultdict

METHOD = 'shared-capacity-proportional-v1'


def _number(value: object, *, maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('Non-numeric GPU telemetry')
    number = float(value)
    if not math.isfinite(number) or number < 0 or (maximum is not None and number > maximum):
        raise ValueError('GPU telemetry out of bounds')
    return number


def estimate_shared_capacity(windows: list[dict], *, device_id: str) -> dict:
    """Allocate observed GPU busy capacity without double counting.

    Windows are nonoverlapping [start,end) on one GPU. Each has a trusted
    external global utilization ratio in [0,1], or None for unavailable.
    Active jobs provide nonnegative HIP activity weights, not billing proof.
    Unknown external activity and unavailable utilization make a window
    unallocatable; its capacity is never assigned to MTA jobs.
    """
    if not isinstance(device_id, str) or not device_id or len(device_id) > 160:
        raise ValueError('Invalid GPU identity')
    if not isinstance(windows, list) or len(windows) > 100000:
        raise ValueError('Invalid GPU windows')
    totals = defaultdict(float)
    allocated = 0.0
    observed = 0.0
    skipped = 0
    prior_end = None
    for window in windows:
        if not isinstance(window, dict) or set(window) != {
            'start', 'end', 'utilization', 'jobs', 'external_activity'
        }:
            raise ValueError('Invalid GPU window')
        start, end = _number(window['start']), _number(window['end'])
        if end <= start or (prior_end is not None and start < prior_end):
            raise ValueError('GPU windows must be ordered and disjoint')
        prior_end = end
        duration = end - start
        if window['utilization'] is None:
            skipped += 1
            continue
        utilization = _number(window['utilization'], maximum=1.0)
        capacity = duration * utilization
        observed += capacity
        if type(window['external_activity']) is not bool:
            raise ValueError('External activity must be boolean')
        jobs = window['jobs']
        if not isinstance(jobs, dict) or len(jobs) > 10000:
            raise ValueError('Invalid job weights')
        weights = {}
        for job_id, weight in jobs.items():
            if not isinstance(job_id, str) or not job_id or len(job_id) > 128:
                raise ValueError('Invalid job identity')
            weights[job_id] = _number(weight)
        # An active non-MTA process invalidates attribution, rather than
        # allocating its observed consumption to MTA users.
        if window['external_activity'] or not weights or sum(weights.values()) <= 0:
            skipped += 1
            continue
        weight_total = sum(weights.values())
        if not math.isfinite(weight_total):
            raise ValueError('Excessive HIP weights')
        for job_id, weight in weights.items():
            totals[job_id] += capacity * (weight / weight_total)
        allocated += capacity
    return {
        'method': METHOD,
        'device_id': device_id,
        'unit': 'estimated_gpu_equivalent_seconds',
        'job_estimates': dict(sorted(totals.items())),
        'observed_capacity_seconds': observed,
        'allocated_capacity_seconds': allocated,
        'unallocated_capacity_seconds': max(0.0, observed - allocated),
        'skipped_windows': skipped,
        'billing_eligible': False,
        'resource_source': 'diagnostic-shared-gpu-estimate',
        'reason': 'Capacity allocation estimate, not certified GPU engine time or energy',
    }
