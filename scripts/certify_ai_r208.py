#!/usr/bin/env python3
"""Non-destructive, offline certification gate for MTA AI r208.

Exit 0 only for static gate checks; full certification always requires
separate integration / hardware evidence. Does not invoke server services.
"""
import argparse
import ast
import json
import pathlib
import platform
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def static_gate():
    queue = ROOT / 'app/ai_arranger_runtime.py'
    ledger = ROOT / 'app/ai_billing.py'
    tree = ast.parse(queue.read_text(encoding='utf-8'))
    billing = ast.parse(ledger.read_text(encoding='utf-8'))
    funcs = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    ledger_funcs = {n.name for n in billing.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    return {
        'queue_receipt_reader': 'terminal_receipt' in funcs,
        'queue_recovery': 'recover_queued' in funcs,
        'ledger_idempotent_finish': 'finish_job_idempotent' in ledger_funcs,
        'terminal_receipt_is_not_cross_database_commit': True,
    }


def hardware_probe():
    def capture(argv):
        if not shutil.which(argv[0]):
            return {'available': False, 'reason': f'{argv[0]} not installed'}
        try:
            p = subprocess.run(argv, capture_output=True, text=True, timeout=15, check=False)
            return {'available': True, 'exit_code': p.returncode,
                    'stdout': p.stdout[-2500:], 'stderr': p.stderr[-800:]}
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {'available': False, 'reason': str(exc)}
    result = {'kernel': platform.release(), 'system': platform.platform(),
              'amd_smi': capture(['amd-smi', 'list']), 'rocminfo': capture(['rocminfo'])}
    # Import torch in a subprocess to keep unavailable HIP libraries from crashing probe.
    result['torch_hip'] = capture([sys.executable, '-c',
        'import json,torch; print(json.dumps({"hip":torch.version.hip,"cuda_available":torch.cuda.is_available(),"devices":[torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]}))'])
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--hardware', action='store_true', help='Read local hardware only; never contact or modify services')
    p.add_argument('--output', type=pathlib.Path)
    args = p.parse_args()
    checks = static_gate()
    report = {
        'project': 'MTA Audio Editor', 'version': '0.3.0-r208',
        'static_checks': checks,
        'end_to_end_atomicity': 'NOT_CERTIFIED',
        'reason': 'SQLite queue receipt, separate billing ledger and audio filesystem do not share an atomic commit protocol',
        'required_evidence': [
            'Crash injection at each boundary: audio staging, publication, receipt commit, billing finalization',
            'Recovery replay across server restart with unique published output and one ledger settlement',
            'Concurrent worker cancellation and billing retry under database lock contention',
            'Execution of real adapters on Rocky EL10 ROCm 7.2.4 gfx1151 with measurements and cancellation',
        ],
        'hardware_certification': 'NOT_CERTIFIED',
    }
    if args.hardware:
        report['local_hardware_probe'] = hardware_probe()
    out = json.dumps(report, indent=2, ensure_ascii=False) + '\n'
    if args.output:
        args.output.write_text(out, encoding='utf-8')
    else:
        print(out)
    return 0 if all(checks.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
