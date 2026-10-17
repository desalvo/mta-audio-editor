"""Task-scoped ROCm kernel activity diagnostics. Never billing evidence."""
from __future__ import annotations
import functools
import json
import math
import logging
import os
from pathlib import Path
import re
import tempfile
import threading
import time
from collections import OrderedDict

STATUSES = frozenset(('profiling', 'profiled_kernels_diagnostic', 'profiler_unavailable',
                      'profiler_no_gpu_events', 'profiler_failed'))
LOGGER = logging.getLogger(__name__)
_TASK = re.compile(r'[A-Za-z0-9_-]{1,128}')


def kernel_activity(trace: dict, wall_seconds: float) -> tuple[float, int, int]:
    """Union GPU kernel intervals; exclude CPU/HIP API spans and copies.

    A single device is required. A diagnostic kernel-active interval is neither
    elapsed stream time nor certified exclusive/invoiceable GPU usage.
    """
    events = trace.get('traceEvents')
    if not isinstance(events, list) or len(events) > 1_000_000:
        raise ValueError('Invalid or oversized profiler event list')
    intervals = []
    devices = set()
    for event in events:
        if not isinstance(event, dict) or event.get('ph') != 'X' or event.get('cat') not in ('kernel', 'gpu_kernel'):
            continue
        args = event.get('args')
        device = args.get('device') if isinstance(args, dict) else None
        start, duration = event.get('ts'), event.get('dur')
        if type(device) is not int or device < 0:
            raise ValueError('GPU event has no device identity')
        if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or x < 0 for x in (start, duration)):
            raise ValueError('Invalid GPU event interval')
        if duration:
            intervals.append((start, start + duration))
            devices.add(device)
    if not intervals:
        return 0.0, 0, 0
    if len(devices) != 1:
        raise ValueError('Multi-device profile not supported')
    intervals.sort()
    total = 0.0
    left, right = intervals[0]
    for start, end in intervals[1:]:
        if start <= right:
            right = max(right, end)
        else:
            total += right - left
            left, right = start, end
    total = (total + right - left) / 1_000_000
    if not math.isfinite(wall_seconds) or wall_seconds < 0 or total > wall_seconds * 1.1 + .05:
        raise ValueError('Kernel intervals exceed capture wall time')
    return total, len(intervals), next(iter(devices))


class TaskProfiler:
    def __init__(self, torch_loader=None, clock=time.monotonic, *, source='ace-torch-profiler',
                 on_update=None, live_interval=5):
        if source not in ('ace-torch-profiler', 'torch-profiler'):
            raise ValueError('Unsupported profiler source')
        self.source = source
        self._on_update = on_update
        self._live_interval = max(2.0, float(live_interval))
        self._loader = torch_loader or self._torch
        self._clock = clock
        self._capture_lock = threading.Lock()
        self._records_lock = threading.Lock()
        self._records = OrderedDict()

    @staticmethod
    def _torch():
        import torch
        return torch

    def _save(self, task, record):
        with self._records_lock:
            self._records[task] = (self._clock(), dict(record))
            self._records.move_to_end(task)
            while len(self._records) > 128:
                self._records.popitem(last=False)
        if self._on_update is not None:
            try:
                self._on_update(dict(record))
            except Exception as exc:
                LOGGER.warning('MTA diagnostic report unavailable: %s', type(exc).__name__)

    @staticmethod
    def _trace(profile, wall):
        fd, name = tempfile.mkstemp(prefix='mta-gpu-profile-', suffix='.json')
        os.close(fd)
        try:
            profile.export_chrome_trace(name)
            path = Path(name)
            if path.stat().st_size > 64 * 1024 * 1024:
                raise ValueError('Profiler trace exceeds diagnostic limit')
            return kernel_activity(json.loads(path.read_text()), wall)
        finally:
            Path(name).unlink(missing_ok=True)

    def get(self, task):
        with self._records_lock:
            value = self._records.get(task)
            return dict(value[1]) if value and self._clock() - value[0] <= 3600 else None

    def wrap(self, generate):
        @functools.wraps(generate)
        def measured(*args, **kwargs):
            task = kwargs.get('job_id')
            if not isinstance(task, str) or not _TASK.fullmatch(task):
                return generate(*args, **kwargs)
            # Serialize profiled generations, so their process-wide capture cannot
            # overlap another wrapped inference. Upstream single-worker is required.
            with self._capture_lock:
                try:
                    from . import ai_gpu_verified as verified
                except ImportError:
                    import ai_gpu_verified as verified
                if verified.readiness()['ready']:
                    initial={'task_id':task,'source':self.source,'status':'profiling','billing_eligible':False}
                    self._save(task,initial)
                    def publish(evidence):
                        value=evidence['payload']
                        self._save(task,{**initial,'status':'profiled_kernels_diagnostic' if value['kernel_count'] else 'profiler_no_gpu_events',
                            'gpu_active_seconds':value['gpu_seconds'],'wall_seconds':value['wall_seconds'],
                            'kernel_count':value['kernel_count'],'device_id':value['device_id'],'billing_evidence':evidence})
                    try:return verified.measured(task,lambda:generate(*args,**kwargs),publish=publish)
                    finally:
                        if self.get(task).get('status')=='profiling':self._save(task,{**initial,'status':'profiler_failed'})
                record = {'task_id': task, 'source': self.source,
                          'status': 'profiling', 'billing_eligible': False}
                self._save(task, record)
                profile = None
                try:
                    torch = self._loader()
                    activity = torch.profiler.ProfilerActivity.CUDA
                    if not torch.version.hip or not torch.cuda.is_available() or activity not in torch.profiler.supported_activities():
                        raise RuntimeError('ROCm GPU profiling unavailable')
                    torch.cuda.synchronize()
                    profile = torch.profiler.profile(activities=[activity], record_shapes=False,
                        profile_memory=False, with_stack=False)
                    profile.start()
                except Exception as exc:
                    LOGGER.warning('MTA GPU profiler unavailable: %s', type(exc).__name__)
                    # Profiling must not suppress or rerun an otherwise working job.
                    if profile is not None:
                        try: profile.stop()
                        except Exception as exc:
                            LOGGER.debug('MTA profiler initialization cleanup: %s', type(exc).__name__)
                    profile = None
                    record['status'] = 'profiler_unavailable'
                started = self._clock()
                segment_started = started
                seconds_total, count_total, device_seen = 0.0, 0, None
                owner = threading.get_ident()
                checkpoint_busy = False
                hook = None
                is_compiling = getattr(getattr(torch, 'compiler', None), 'is_compiling', lambda: False) if profile is not None else lambda: False

                def collect_segment():
                    nonlocal profile, seconds_total, count_total, device_seen
                    previous, profile = profile, None
                    try:
                        torch.cuda.synchronize()
                        finished = self._clock()
                    finally:
                        previous.stop()
                    seconds, count, device = self._trace(previous, max(0.0, finished - segment_started))
                    if count and device_seen is not None and device_seen != device:
                        raise ValueError('GPU device changed between profiling windows')
                    if count:
                        device_seen = device
                    seconds_total += seconds
                    count_total += count
                    record.update(gpu_active_seconds=round(seconds_total, 6), kernel_count=count_total,
                                  device_id=device_seen or 0, wall_seconds=max(0.0, finished - started))

                def checkpoint(*unused):
                    nonlocal profile, segment_started, checkpoint_busy
                    if is_compiling():
                        return  # Do not trace profiler control into a compiled model.
                    if (profile is None or checkpoint_busy or threading.get_ident() != owner
                            or self._clock() - segment_started < self._live_interval):
                        return
                    checkpoint_busy = True
                    try:
                        collect_segment()
                        self._save(task, record)
                        profile = torch.profiler.profile(activities=[activity], record_shapes=False,
                            profile_memory=False, with_stack=False)
                        profile.start()
                        segment_started = self._clock()
                    except Exception as exc:
                        if profile is not None:
                            try: profile.stop()
                            except Exception as cleanup:
                                LOGGER.debug('MTA checkpoint cleanup: %s', type(cleanup).__name__)
                        profile = None
                        record['status'] = 'profiler_failed'
                        LOGGER.warning('MTA live GPU capture failed: %s', type(exc).__name__)
                    finally:
                        checkpoint_busy = False

                if profile is not None:
                    try:
                        # Runs on the inference thread at model boundaries. Never
                        # stop/export an active profiler from the HTTP thread.
                        hook = torch.nn.modules.module.register_module_forward_pre_hook(checkpoint)
                    except Exception as exc:
                        LOGGER.debug('MTA model checkpoints unavailable: %s', type(exc).__name__)
                        # Runtime without hooks retains end-of-task collection.
                try:
                    return generate(*args, **kwargs)
                finally:
                    if hook is not None:
                        try: hook.remove()
                        except Exception as cleanup:
                            LOGGER.debug('MTA hook cleanup: %s', type(cleanup).__name__)
                    if profile is not None:
                        try:
                            collect_segment()
                            record['status'] = 'profiled_kernels_diagnostic' if count_total else 'profiler_no_gpu_events'
                        except Exception as exc:
                            LOGGER.warning('MTA GPU profiler capture failed: %s', type(exc).__name__)
                            record['status'] = 'profiler_failed'
                    self._save(task, record)
        return measured


def parse_report(payload, expected_task, *, source='ace-torch-profiler'):
    """Accept a matching backend report only as nonbillable diagnostics."""
    if (not isinstance(expected_task, str) or not _TASK.fullmatch(expected_task)
            or not isinstance(payload, dict) or payload.get('task_id') != expected_task
            or source not in ('ace-torch-profiler', 'torch-profiler')
            or payload.get('source') != source or payload.get('billing_eligible') is not False
            or not isinstance(payload.get('status'), str) or payload['status'] not in STATUSES):
        raise ValueError('Invalid or mismatched GPU profiler report')
    status = payload['status']
    result = {'gpu_metrics_status': status, 'gpu_metrics_source': source}
    if status == 'profiled_kernels_diagnostic' or (status == 'profiling' and payload.get('gpu_active_seconds', 0)):
        seconds, wall = payload.get('gpu_active_seconds'), payload.get('wall_seconds')
        if any(isinstance(x, bool) or not isinstance(x, (float, int)) or not math.isfinite(x) or x <= 0 for x in (seconds, wall)):
            raise ValueError('Invalid profiler duration')
        if seconds > wall * 1.1 + .05 or type(payload.get('kernel_count')) is not int or payload['kernel_count'] <= 0 or type(payload.get('device_id')) is not int or payload['device_id'] < 0:
            raise ValueError('Invalid profiler evidence')
        result['gpu_seconds_estimated'] = float(seconds)
    return result
