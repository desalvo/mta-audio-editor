#!/usr/bin/env python3
"""Opt-in ACE-Step 0.1.8 launcher; no upstream source edits or billing authority."""
from __future__ import annotations
import inspect
import os
from pathlib import Path
import sys

if __package__:
    from .ace_gpu_profiler import TaskProfiler
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from ace_gpu_profiler import TaskProfiler


def install(server, profiler=None):
    from fastapi import Depends, HTTPException
    if os.getenv('ACESTEP_QUEUE_WORKERS', '1') != '1':
        raise RuntimeError('MTA diagnostic profiler requires ACESTEP_QUEUE_WORKERS=1')
    target = server.run_blocking_generate
    if 'job_id' not in inspect.signature(target).parameters:
        raise RuntimeError('Unsupported ACE-Step task execution interface')
    profiler = profiler or TaskProfiler()
    server.run_blocking_generate = profiler.wrap(target)

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
    import acestep.api_server as server
    install(server)
    server.main()


if __name__ == '__main__':
    main()
