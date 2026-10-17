#!/usr/bin/env python3
"""Calibrate or inspect per-task GPU billing as the MTA service user.

Use the same accelerator Python, user and MTA_GPU_BILLING_ROOT as the server
and ACE service. No price changes, invoices or service restarts are performed.
"""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('status','calibrate','disable'))
    args=parser.parse_args()
    from app import ai_gpu_verified as gpu
    try:
        if args.action=='calibrate':
            import torch
            result=gpu.calibrate(torch)
        elif args.action=='disable':
            (gpu.root()/'policy.json').unlink(missing_ok=True)
            result=gpu.readiness()
        else:result=gpu.readiness()
        print(json.dumps(result,sort_keys=True))
        return 0 if args.action=='disable' or result['ready'] else 2
    except (OSError,ValueError,RuntimeError,ImportError) as exc:
        print(json.dumps({'ready':False,'error':type(exc).__name__,'reason':str(exc)}))
        return 2


if __name__=='__main__':sys.exit(main())
