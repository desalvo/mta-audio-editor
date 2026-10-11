#!/usr/bin/env python3
"""Standalone ACE-Step GPU capability benchmark, no MTA server required.

Samples vendor tools during one ACE-Step CLI generation. Results are diagnostic,
not certified per-job energy consumption. Never reads API credentials.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


def run(args, timeout=12):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
        return {"rc": p.returncode, "stdout": p.stdout[:16000], "stderr": p.stderr[:1200]}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"error": str(error)[:200]}


def vendor():
    amd = Path('/dev/kfd').exists() or any(p.exists() for p in Path('/sys/class/drm').glob('card*/device/vendor') if p.read_text().strip().lower() == '0x1002')
    nvidia = shutil.which('nvidia-smi') is not None or Path('/proc/driver/nvidia/gpus').exists() or any(p.exists() for p in Path('/sys/class/drm').glob('card*/device/vendor') if p.read_text().strip().lower() == '0x10de')
    if amd and nvidia:
        return 'mixed'
    return 'amd' if amd else 'nvidia' if nvidia else 'unknown'


def process_sample(pids):
    # Only process records belonging to the benchmark's actual process tree.
    output = {}
    for pid in pids:
        info = Path('/proc') / str(pid) / 'fdinfo'
        clients = {}
        try:
            entries = list(info.iterdir())
        except OSError:
            continue
        for entry in entries:
            try:
                content = entry.read_text()
            except (OSError, UnicodeError):
                continue
            pairs = dict(line.split(':', 1) for line in content.splitlines() if ':' in line)
            client = pairs.get('drm-client-id', '').strip()
            driver = pairs.get('drm-driver', '').strip()
            if client and driver:
                key = driver + ':' + client
                clients[key] = {k.strip(): v.strip() for k, v in pairs.items() if k.strip().startswith(('drm-engine-', 'drm-memory-', 'drm-resident-'))}
        if clients:
            output[str(pid)] = clients
    return output


def descendants(root):
    # Linux procfs snapshot. Tracking is best effort; very short processes may escape.
    parents = {}
    for status in Path('/proc').glob('[0-9]*/status'):
        try:
            text = status.read_text()
            parent = next(int(x.split(':', 1)[1].strip()) for x in text.splitlines() if x.startswith('PPid:'))
            parents[int(status.parent.name)] = parent
        except (OSError, ValueError, StopIteration):
            pass
    tree = {root}
    for _ in range(16):
        new = tree | {pid for pid, ppid in parents.items() if ppid in tree}
        if new == tree:
            break
        tree = new
    return tree


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ace-root', default=os.environ.get('MTA_BASE', '/opt/mta') + '/ace-step')
    p.add_argument('--python', default=os.environ.get('MTA_BASE', '/opt/mta') + '/venv-ace-step/bin/python')
    p.add_argument('--config', help='Existing ACE-Step CLI TOML; if omitted create a minimal test configuration')
    p.add_argument('--output-dir', default='./ace-gpu-benchmark')
    p.add_argument('--interval', type=float, default=0.5)
    p.add_argument('--timeout', type=int, default=900)
    p.add_argument('--probe-only', action='store_true', help='Detect devices/tools without running inference')
    args = p.parse_args()
    if not sys.platform.startswith('linux'):
        p.error('Linux only')
    if not 0.1 <= args.interval <= 10 or not 10 <= args.timeout <= 7200:
        p.error('invalid interval/timeout')
    out = Path(args.output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    hardware = vendor()
    commands = {'nvidia_gpu': ['nvidia-smi', '--query-gpu=index,uuid,name,driver_version,power.draw,utilization.gpu,memory.used', '--format=csv,noheader,nounits'],
                'nvidia_processes': ['nvidia-smi', '--query-compute-apps=pid,gpu_uuid,used_gpu_memory', '--format=csv,noheader,nounits'],
                'amd_devices': ['amdgpu_top', '--list'],
                'amd_info': ['amdgpu_top', '--json', '--dump']}
    meta = {'schema': 1, 'vendor': hardware, 'time_utc': datetime.now(timezone.utc).isoformat(),
            'kernel': run(['uname', '-r']), 'cgroup_v2': Path('/sys/fs/cgroup/cgroup.controllers').exists(),
            'tools': {k: run(cmd) if shutil.which(cmd[0]) else {'available': False} for k, cmd in commands.items()},
            'limitations': ['Samples can miss short-lived child processes',
                            'GPU power readings are DEVICE-wide, never attributed to the benchmark job',
                            'Per-process DRM counter support depends on driver and permissions',
                            'Output is diagnostic only and must not be used for automatic billing']}
    (out / 'gpu-info.json').write_text(json.dumps(meta, indent=2) + '\n')
    if args.probe_only:
        print('Probe JSON:', out / 'gpu-info.json')
        return 0
    root = Path(args.ace_root)
    py = Path(args.python)
    if not (root / 'cli.py').is_file() or not py.is_file():
        p.error('ACE-Step installation not found; install ACE-Step first or pass --ace-root and --python')
    if args.config:
        config = Path(args.config).expanduser().resolve()
        if not config.is_file():
            p.error('ACE-Step TOML config does not exist')
    else:
        config = out / 'benchmark.toml'
        # ACE-Step merges these with defaults; no interactive input required.
        config.write_text('task_type = "text2music"\ncaption = "Instrumental electronic music with drums, bass and synthesizers"\nlyrics = "[Instrumental]"\ninstrumental = true\nsample_mode = false\nthinking = false\nduration = 30.0\nbatch_size = 1\ninference_steps = 8\naudio_format = "wav"\nsave_dir = ' + json.dumps(str(out / 'audio')) + '\n')
    command = [str(py), 'cli.py', '--config', str(config)]
    # Do not include any secrets from environment or ACE configuration in output.
    amd_monitor = None
    monitor_log = None
    if hardware in ('amd', 'mixed') and shutil.which('amdgpu_top'):
        monitor_log = (out / 'amdgpu-top.jsonl').open('w')
        try:
            amd_monitor = subprocess.Popen(['amdgpu_top', '--json', '-s', f'{round(args.interval * 1000)}ms', '-n', str(min(int(args.timeout / args.interval) + 5, 72000))], stdout=monitor_log, stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError:
            monitor_log.close()
            monitor_log = None
    with (out / 'ace-cli.log').open('w') as log:
        proc = subprocess.Popen(command, cwd=root, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        samples = []
        began = time.monotonic()
        while proc.poll() is None and time.monotonic() - began < args.timeout:
            pids = descendants(proc.pid)
            datum = {'elapsed_s': round(time.monotonic() - began, 3), 'pids': sorted(pids), 'drm_by_pid': process_sample(pids)}
            if hardware in ('nvidia', 'mixed'):
                # process-gpu mapping, includes other user processes; correlate with pids.
                datum['nvidia_processes'] = run(commands['nvidia_processes'], timeout=5)
                datum['nvidia_gpu_global_diagnostic_only'] = run(commands['nvidia_gpu'], timeout=5)
            if hardware in ('amd', 'mixed') and shutil.which('amdgpu_top'):
                # JSON dump is static device info; pid DRM fdinfo above is per-process.
                pass
            samples.append(datum)
            time.sleep(args.interval)
        timed_out = proc.poll() is None
        if timed_out:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        result = {'schema': 1, 'vendor': hardware, 'exit_code': proc.returncode,
                  'timed_out': timed_out, 'duration_s': round(time.monotonic() - began, 2),
                  'samples': samples, 'billable': False,
                  'note': 'GPU device-global metrics are diagnostics only; do not charge per-user energy.'}
        (out / 'gpu-activity.json').write_text(json.dumps(result, indent=2) + '\n')
    if amd_monitor is not None:
        if amd_monitor.poll() is None:
            amd_monitor.terminate()
            try:
                amd_monitor.wait(timeout=5)
            except subprocess.TimeoutExpired:
                amd_monitor.kill()
                amd_monitor.wait()
    if monitor_log is not None:
        monitor_log.close()
    print('GPU benchmark report:', out)
    print('Job exit status:', proc.returncode, '| timed out:', timed_out)
    print('Share gpu-info.json and gpu-activity.json after review; audio output is not needed.')
    return 0 if proc.returncode == 0 and not timed_out else 1


if __name__ == '__main__':
    sys.exit(main())
