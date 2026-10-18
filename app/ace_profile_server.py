#!/usr/bin/env python3
"""Opt-in ACE-Step 0.1.8 launcher; no upstream source edits or billing authority."""
from __future__ import annotations
import inspect
import os
from pathlib import Path
import sys

if __package__:
    from .ace_gpu_profiler import TaskProfiler
    from .ace_task_control import TaskControl, SERVICE_GUARD_SECONDS
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from ace_gpu_profiler import TaskProfiler
    from ace_task_control import TaskControl, SERVICE_GUARD_SECONDS


def install(server, profiler=None):
    from fastapi import Depends, HTTPException
    if os.getenv('ACESTEP_QUEUE_WORKERS', '1') != '1':
        raise RuntimeError('MTA diagnostic profiler requires ACESTEP_QUEUE_WORKERS=1')
    target = server.run_blocking_generate
    if 'job_id' not in inspect.signature(target).parameters:
        raise RuntimeError('Unsupported ACE-Step task execution interface')
    profiler = profiler or TaskProfiler()
    controls = TaskControl()
    # Upstream v0.1.8 reads this constant on import. main() sets its environment
    # before import; embedded launchers may already have loaded the module.
    service_module = sys.modules.get('acestep.core.generation.handler.generate_music_execute')
    if service_module is not None:
        service_module._DEFAULT_GENERATION_TIMEOUT = SERVICE_GUARD_SECONDS
    server.run_blocking_generate = controls.wrap(target, profiler)

    @server.app.get('/mta/runtime', dependencies=[Depends(server.verify_api_key)])
    def runtime():
        return {'schema': 'mta-ace-runtime-v1', 'max_timeout_seconds': 14400,
                'task_control': True, 'cancellation': 'cooperative', 'billing_eligible': False}

    @server.app.post('/mta/tasks/{task_id}/control', dependencies=[Depends(server.verify_api_key)])
    def control(task_id: str, body: dict):
        if set(body) - {'timeout_seconds', 'cancel'} or type(body.get('cancel', False)) is not bool:
            raise HTTPException(422, 'Invalid ACE task control')
        try:
            return controls.configure(task_id, timeout_seconds=body.get('timeout_seconds'), cancel=body.get('cancel', False))
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @server.app.get('/mta/tasks/{task_id}/progress', dependencies=[Depends(server.verify_api_key)])
    def task_progress(task_id: str):
        with controls.lock:
            row = controls.tasks.get(task_id)
            if row is None or not row.get('progress'):
                raise HTTPException(404, 'No task progress report')
            return dict(row['progress'])

    @server.app.get('/mta/telemetry/{task_id}', dependencies=[Depends(server.verify_api_key)])
    def telemetry(task_id: str):
        record = profiler.get(task_id)
        if record is None:
            raise HTTPException(404, 'No task profiler report')
        return record
    return profiler


def main():
    # The installed unit runs from the ACE source checkout. `python -m` adds
    # that working directory to sys.path, whereas an external script adds only
    # its own directory. Preserve the original launcher's import semantics for
    # source-only ACE installs, while respecting Python's safe-path option.
    if not sys.flags.safe_path:
        sys.path.insert(0, str(Path.cwd()))
    # Import by its canonical name: upstream's CLI starts uvicorn using this same
    # module/app, preserving the hook in the single server process.
    os.environ['ACESTEP_GENERATION_TIMEOUT'] = str(SERVICE_GUARD_SECONDS)
    import acestep.api_server as server
    # The query route captures this ceiling when create_app() builds routes.
    # Rebuild before lifespan/model initialization, not after service startup.
    server.TASK_TIMEOUT_SECONDS = SERVICE_GUARD_SECONDS
    if callable(getattr(server, 'create_app', None)):
        server.app = server.create_app()
    install(server)
    server.main()


if __name__ == '__main__':
    main()
