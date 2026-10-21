#!/usr/bin/env python3
"""Explicit opt-in, offline MR-MT3 GPU benchmark for a dedicated maintenance window.

Does not deploy, restart services, change server configuration or download assets.
Exit 2 is an incomplete but resumable benchmark; exit 0 means inference finished,
not that model accuracy passed. Reference scoring must be run separately.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def plan_cycles(audio, model, output, windows_per_cycle, max_cycles, minimum_free_gib):
    if not audio.is_file() or not model.is_file():
        raise ValueError('Audio and Safetensors model must exist locally')
    if model.suffix != '.safetensors':
        raise ValueError('Only converted Safetensors model is accepted')
    if not 1 <= windows_per_cycle <= 1000 or not 1 <= max_cycles <= 10000:
        raise ValueError('Invalid cycle limits')
    if not 0 <= minimum_free_gib <= 1024:
        raise ValueError('Invalid free GPU limit')
    if output.is_symlink():
        raise ValueError('Refusing symlink output directory')
    return True


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--audio', required=True, type=Path)
    p.add_argument('--model', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--windows-per-cycle', type=int, default=4)
    p.add_argument('--max-cycles', type=int, default=1000)
    p.add_argument('--min-free-gpu-gib', type=float, default=3)
    p.add_argument('--threads', type=int, default=2)
    p.add_argument('--backend', choices=('cuda','rocm','gpu'), default='gpu',
                   help='cuda=NVIDIA, rocm=AMD ROCm, gpu=accept either without CPU fallback')
    p.add_argument('--allow-production-gpu', action='store_true',
                   help='Explicitly authorize running on a shared production GPU')
    args = p.parse_args(argv)
    plan_cycles(args.audio, args.model, args.output, args.windows_per_cycle,
                args.max_cycles, args.min_free_gpu_gib)
    if not args.allow_production_gpu:
        p.error('GPU execution requires explicit --allow-production-gpu opt-in')
    args.output.mkdir(parents=True, exist_ok=True)
    script = Path(__file__).with_name('run_mrmt3_resumable.py')
    for i in range(args.max_cycles):
        command = [sys.executable, str(script), '--audio', str(args.audio),
                   '--model', str(args.model), '--output', str(args.output),
                   '--device', args.backend, '--min-free-gpu-gib', str(args.min_free_gpu_gib),
                   '--threads', str(args.threads), '--max-windows', str(args.windows_per_cycle)]
        started = time.monotonic()
        run = subprocess.run(command, check=False, timeout=7200,
                             env={**os.environ, 'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1'})
        record = {'cycle':i+1,'exit_code':run.returncode,'elapsed_seconds':round(time.monotonic()-started,2)}
        print(json.dumps(record, sort_keys=True),flush=True)
        if run.returncode == 0:
            print('Inference completed; quality NOT certified without ground truth scoring.',flush=True)
            return 0
        if run.returncode != 2:
            return run.returncode
    print('Incomplete: cycle limit reached, rerun with same output to resume.',flush=True)
    return 2

if __name__ == '__main__':
    sys.exit(main())
