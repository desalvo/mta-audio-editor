"""Task-local ACE stages and observed DiT forward evaluations; never billing."""
from __future__ import annotations
from contextlib import contextmanager
import math
import threading


def safe_progress(value, task):
    if not isinstance(value, dict) or value.get('task_id') != task:
        return {}
    percent = value.get('progress_percent')
    if isinstance(percent, bool) or not isinstance(percent, (int, float)) or not math.isfinite(percent) or not 0 <= percent < 100:
        return {}
    source = value.get('progress_source')
    if source not in ('ace-stage-estimate', 'ace-dit-evaluations'):
        return {}
    result = {'progress_percent': percent, 'progress_source': source, 'progress_estimated': True}
    for key in ('steps_completed', 'steps_total'):
        n = value.get(key)
        if type(n) is int and 0 <= n <= 1000:
            result[key] = n
    if ('steps_completed' in result) != ('steps_total' in result):
        return {}
    if 'steps_total' in result and result['steps_total'] <= 0:
        return {}
    if result.get('steps_completed', 0) > result.get('steps_total', 0):
        return {}
    return result


def stage(percent):
    if percent < 15: return 'Preparing / Preparazione'
    if percent < 52: return 'Encoding source / Codifica sorgente'
    if percent < 80: return 'DiT diffusion / Diffusione DiT'
    if percent < 95: return 'Decoding / Decodifica'
    return 'Finalizing backend audio / Finalizzazione audio'


def update(control, task, fraction):
    if isinstance(fraction, bool) or not isinstance(fraction, (int, float)) or not math.isfinite(fraction):
        return
    percent = max(0, min(99, fraction*100))
    with control.lock:
        row = control._record(task)
        old = row.get('progress', {})
        # Upstream's diffusion timer is an estimate. Observed model evaluations
        # take precedence during the same phase; never infer input audio position.
        if old.get('progress_source') == 'ace-dit-evaluations' and 52 <= percent < 80:
            return
        if percent < old.get('progress_percent', 0):
            return
        row['progress'] = {'task_id': task, 'progress_percent': percent,
            'progress_source': 'ace-stage-estimate', 'progress_estimated': True}


@contextmanager
def observe_decoder(control, task, handler, service_kwargs):
    """Known v0.1.8 turbo Euler path: one decoder forward evaluation per step.

    Counts Python forward completions, not synchronized GPU completion. The
    weighted whole-job percent remains an estimate; arbitrary models fall back.
    """
    model = getattr(handler, 'model', None)
    model = getattr(model, '_orig_mod', model)
    decoder = getattr(model, 'decoder', None)
    name = type(model).__module__
    total = service_kwargs.get('infer_steps')
    supported = (name.endswith('modeling_acestep_v15_turbo') and type(total) is int
        and total > 0 and service_kwargs.get('timesteps') is None
        and service_kwargs.get('sampler_mode', 'euler') == 'euler'
        and not service_kwargs.get('cover_noise_strength', 0)
        and not service_kwargs.get('flow_edit_morph', False))
    register = getattr(decoder, 'register_forward_hook', None)
    hook = None
    if supported and callable(register):
        owner, count, total = threading.get_ident(), [0], min(total, 20)
        def completed(*unused):
            if threading.get_ident() != owner:
                return
            count[0] += 1
            with control.lock:
                row = control._record(task)
                if count[0] > total:
                    # Incompatible runtime: invalidate this ratio, don't invent.
                    row.pop('progress', None)
                    return
                row['progress'] = {'task_id': task, 'progress_percent': 52+27*count[0]/total,
                    'progress_source': 'ace-dit-evaluations', 'progress_estimated': True,
                    'steps_completed': count[0], 'steps_total': total}
        try:
            hook = register(completed)
        except Exception:
            hook = None  # Optional observation must not prevent audio generation.
    try:
        yield
    finally:
        if hook is not None:
            try:
                hook.remove()
            except Exception:
                hook = None  # Optional observation must not fail the underlying job.
