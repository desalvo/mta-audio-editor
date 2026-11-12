"""Read-only job statistics, never consumption, quota or settlement evidence."""
import math
import time


def number(value):
    return float(value) if type(value) in (int, float) and math.isfinite(value) and 0 <= value < 1e18 else None


def project(value, *, now=None, live_gpu=False):
    result = dict(value)
    state = result.get('state', result.get('status'))
    measured = number(result.get('gpu_seconds'))
    observed = number(result.get('gpu_seconds_estimated'))
    partial = state == 'running' and result.get('resource_metrics_partial', False)
    if measured is not None and (not partial or number(result.get('started_at')) is None):
        estimated = result.get('gpu_metrics_source') == 'diagnostic-estimate'
        seconds, source = measured, 'accepted-estimate' if estimated else 'measurement'
    elif observed is not None and (state != 'running' or live_gpu or number(result.get('started_at')) is None):
        seconds, source, estimated = observed, 'telemetry', True
    elif state in ('queued', 'blocked') or number(result.get('started_at')) is None:
        seconds, source, estimated = 0.0, 'not-started', True
    else:
        start = number(result.get('started_at'))
        end = number(result.get('completed_at', result.get('finished_at')))
        if state == 'running':
            end = number(time.time() if now is None else now)
        duration = max(0.0, end-start) if end is not None else number(result.get('elapsed_seconds'))
        if duration is None and number(result.get('wall_ms')) is not None:
            duration = result['wall_ms']/1000
        seconds = max(duration or 0.0, measured or 0.0, observed or 0.0)
        source, estimated = ('job-duration' if duration is not None else 'duration-unavailable'), True
    result['gpu_statistics'] = {'seconds':seconds, 'estimated':estimated, 'source':source, 'billable':False}
    return result


def aggregate(items):
    stats = [item['gpu_statistics'] for item in items if isinstance(item.get('gpu_statistics'), dict)]
    return {'seconds':sum(number(s.get('seconds')) or 0 for s in stats),
            'estimated':any(s.get('estimated') for s in stats),
            'estimated_jobs':sum(bool(s.get('estimated')) for s in stats),
            'duration_estimated_jobs':sum(s.get('source') == 'job-duration' for s in stats),
            'billable':False}
