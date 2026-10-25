"""Deterministic, conservative, period-end shared-infrastructure cost allocation.

This module computes draft contribution statements; it never charges users,
posts credits or changes the immutable hardware usage ledger.
"""
from __future__ import annotations



def allocate_period(cost_cents: int, usage_units: dict[str, int]) -> dict[str, int]:
    """Allocate documented recoverable cents using the largest-remainder rule.

    Only positive measured usage participates. Reject corrupt, negative and
    boolean inputs; zero use means zero recovery (not an invented charge).
    """
    if type(cost_cents) is not int or cost_cents < 0:
        raise ValueError('cost_cents must be a non-negative integer')
    if not isinstance(usage_units, dict) or not all(
        isinstance(k, str) and k and type(v) is int and v >= 0
        for k, v in usage_units.items()
    ):
        raise ValueError('usage_units must map account IDs to non-negative integers')
    result = {k: 0 for k in sorted(usage_units)}
    total = sum(usage_units.values())
    if total == 0 or cost_cents == 0:
        return result
    # Integer-only arithmetic ensures reproducible, cent-exact results.
    remainders = []
    allocated = 0
    for key in sorted(usage_units):
        numerator = cost_cents * usage_units[key]
        share, rem = divmod(numerator, total)
        result[key] = share
        allocated += share
        remainders.append((-rem, key))
    for _, key in sorted(remainders)[:cost_cents - allocated]:
        result[key] += 1
    if sum(result.values()) != cost_cents:
        raise ValueError('Allocation does not conserve documented costs')
    return result


def remaining_recoverable_cents(documented_cost_cents: int, recovered_cents: int) -> int:
    """Prevent repeated drafts from recovering more than documented costs."""
    if (type(documented_cost_cents) is not int or documented_cost_cents < 0
            or type(recovered_cents) is not int or recovered_cents < 0
            or recovered_cents > documented_cost_cents):
        raise ValueError('Invalid cost-recovery ledger totals')
    return documented_cost_cents - recovered_cents


def preview_from_metered_jobs(connection, *, start: int, end: int,
                              documented_cost_cents: int, recovered_cents: int = 0,
                              operator_cost_exclusion_confirmed: bool = False) -> dict:
    """Preview CPU/GPU proportional cost recovery, without recording or collecting money.

    Reject incomplete, unmetered or corrupted jobs rather than silently charging
    the other users for missing observations. Units are milliseconds, derived
    from measured CPU/GPU seconds, to allow integer-only cent allocation.
    """
    import json
    import math

    if (type(start) is not int or type(end) is not int or start < 0 or end <= start):
        raise ValueError('Invalid accounting period')
    ceiling = remaining_recoverable_cents(documented_cost_cents, recovered_cents)
    if type(operator_cost_exclusion_confirmed) is not bool:raise ValueError('Invalid operator cost exclusion confirmation')
    from .worker_loss_resolution import period_losses
    losses=period_losses(connection,start,end)
    if losses and not operator_cost_exclusion_confirmed:
        raise ValueError('Documented eligible costs must explicitly exclude operator-assumed losses')
    tables = {row[0] for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    if 'ai_compute_jobs' not in tables:
        raise ValueError('Missing measured job ledger')
    columns = {row[1] for row in connection.execute('PRAGMA table_info(ai_compute_jobs)')}
    required = {'id', 'user_id', 'started_at', 'status', 'usage_json', 'resource_source', 'billable'}
    if not required <= columns:
        raise ValueError('Incomplete measured job ledger')
    query=("SELECT id,user_id,status,usage_json,resource_source FROM ai_compute_jobs WHERE started_at>=? AND started_at<? AND billable=1 AND accounting_excluded=0"
           if 'accounting_excluded' in columns else
           "SELECT id,user_id,status,usage_json,resource_source FROM ai_compute_jobs WHERE started_at>=? AND started_at<? AND billable=1")
    rows = connection.execute(query,(start,end))
    totals: dict[str, int] = {}
    count = 0
    for job_id, user_id, status, raw, source in rows:
        if status not in ('done','completed','success','succeeded','failed','cancelled','canceled'):
            raise ValueError('Unsettled job in accounting period')
        if source not in ('worker','cgroup','gpu-agent','gpu-kernel-verified','remote-worker'):
            raise ValueError('Unverified resource measurement')
        try:
            usage = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError('Invalid resource measurement') from exc
        if not isinstance(usage, dict):
            raise ValueError('Invalid resource measurement')
        milliseconds = 0
        for field in ('cpu_seconds', 'gpu_seconds'):
            value = usage.get(field, 0)
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError('Invalid measured duration')
            if field=='gpu_seconds' and value and source not in ('gpu-agent','gpu-kernel-verified'):
                raise ValueError('Unverified GPU resource measurement')
            milliseconds += round(value * 1000)
        if type(user_id) is not int or user_id <= 0:
            raise ValueError('Invalid account reference')
        account = str(user_id)
        totals[account] = totals.get(account, 0) + milliseconds
        count += 1
    allocated = allocate_period(ceiling, totals)
    return {'start': start, 'end': end, 'currency': 'EUR', 'draft': True,
            'documented_cost_cents': documented_cost_cents,
            'already_recovered_cents': recovered_cents,
            'max_new_recovery_cents': ceiling,
            'jobs_count': count, 'measured_milliseconds': totals,
            'contribution_cents': allocated,
            'total_draft_cents': sum(allocated.values()),
            'posting_enabled': False,'operator_losses':losses,
            'operator_cost_exclusion_confirmed':bool(losses and operator_cost_exclusion_confirmed)}
