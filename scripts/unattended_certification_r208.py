#!/usr/bin/env python3
"""MTA r208 unattended, non-destructive, cross-platform certification runner.

Stdlib only. Does not install dependencies, start services, change projects or
perform billing transactions. Hardware probes read local device information.
Exit 0 iff all requested mandatory checks pass; 1 on failures/timeouts;
2 if required checks are skipped for missing dependencies.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def tail(path: Path, limit=5000):
    try:
        with path.open('rb') as stream:
            stream.seek(0, 2)
            stream.seek(max(0, stream.tell()-limit))
            return stream.read().decode('utf-8', 'replace')
    except OSError:
        return ''


def execute(name, argv, cwd, results, timeout, log_dir, missing=None):
    path = log_dir / (name + '.log')
    started = time.monotonic()
    if missing:
        entry = {'name': name, 'status': 'SKIP', 'reason': missing, 'command': argv}
    else:
        try:
            with path.open('wb') as logfile:
                proc = subprocess.Popen(argv, cwd=str(cwd), stdout=logfile,
                                        stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                        shell=False)
                try:
                    code = proc.wait(timeout=timeout)
                    status = 'PASS' if code == 0 else 'FAIL'
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.communicate()
                    code = None
                    status = 'TIMEOUT'
            entry = {'name': name, 'status': status, 'exit_code': code,
                     'command': argv, 'log': str(path), 'tail': tail(path)}
        except (OSError, ValueError) as err:
            entry = {'name': name, 'status': 'FAIL', 'error': str(err), 'command': argv}
    entry['duration_seconds'] = round(time.monotonic()-started, 3)
    results.append(entry)
    print(f"[{entry['status']}] {name} ({entry['duration_seconds']} s)", flush=True)
    return entry


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--profile', choices=('quick','full','hardware'), default='full')
    ap.add_argument('--root', type=Path, default=ROOT)
    ap.add_argument('--output', type=Path, help='Report directory (default: project/certification-results)')
    ap.add_argument('--timeout', type=int, default=8400, help='Seconds per test phase, default 140 minutes')
    ap.add_argument('--hardware-required', action='store_true', help='Fail if hardware tools absent')
    ap.add_argument('--archive', type=Path, help='Optional project ZIP to check against adjacent .zip.sha256')
    args = ap.parse_args(argv)
    root = args.root.resolve()
    out = (args.output or root / 'certification-results').resolve()
    out.mkdir(parents=True, exist_ok=True)
    results = []
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    os_info = {'system': platform.system(), 'release': platform.release(),
               'architecture': platform.machine(), 'python': sys.version, 'executable': sys.executable}
    try:
        version = (root / 'VERSION').read_text().strip()
        revision = (root / 'REVISION').read_text().strip()
        ok = version == '0.3.0' and revision == '208'
        results.append({'name': 'version', 'status': 'PASS' if ok else 'FAIL',
                        'version': version, 'revision': revision})
    except OSError as e:
        results.append({'name': 'version', 'status': 'FAIL', 'error': str(e)})
    if args.archive:
        archive = args.archive.resolve()
        try:
            checksum = hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest()
            sf = archive.with_suffix(archive.suffix + '.sha256')
            expected = sf.read_text().split()[0].lower() if sf.exists() else None
            with zipfile.ZipFile(archive) as z:
                corrupt = z.testzip()
            good = (corrupt is None and expected == checksum)
            results.append({'name': 'archive_integrity', 'status': 'PASS' if good else 'FAIL',
                            'sha256': checksum, 'expected_sha256': expected, 'bad_member': corrupt})
        except (OSError, zipfile.BadZipFile, ValueError) as e:
            results.append({'name': 'archive_integrity', 'status': 'FAIL', 'error': str(e)})
    cert = root / 'scripts' / 'certify_ai_r208.py'
    execute('static_ai_gate', [sys.executable, str(cert), '--output', str(out/'static-gate.json')],
            root, results, min(args.timeout, 120), out,
            missing=None if cert.exists() else 'Static certification script missing')
    if args.profile == 'quick':
        test_args = [sys.executable, '-m', 'pytest', '-q', '--maxfail=1', 'tests/test_r208_billing_telemetry_validation.py']
        # Do not assume a particular module exists in old archives.
        if not (root / test_args[-1]).exists():
            test_args = [sys.executable, '-m', 'pytest', '-q', '--maxfail=1', 'tests/test_r208_stem_crossplatform_name_collisions.py']
    elif args.profile == 'full':
        test_args = [sys.executable, '-m', 'pytest', '-q', '--maxfail=1', 'tests']
    else:
        test_args = None
    if test_args is not None:
        pytest_present = subprocess.run([sys.executable, '-c', 'import pytest'],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                        timeout=20, check=False).returncode == 0
        execute('pytest_'+args.profile, test_args, root, results, args.timeout, out,
                missing=None if pytest_present else 'pytest not installed in the selected Python environment')
    if args.profile in ('full', 'hardware'):
        execute('hardware_probe', [sys.executable, str(cert), '--hardware', '--output', str(out/'hardware-probe.json')],
                root, results, min(args.timeout, 120), out,
                missing=None if cert.exists() else 'Hardware probe script missing')
        # Hardware probes only check availability, not GPU workloads or billing end-to-end.
        hw = json.loads((out/'hardware-probe.json').read_text()) if (out/'hardware-probe.json').is_file() else {}
        if args.hardware_required:
            probes = hw.get('hardware', {})
            ok = any(isinstance(probes.get(key), dict) and probes[key].get('available')
                     and probes[key].get('exit_code') == 0 for key in ('rocminfo', 'amd_smi', 'torch_hip'))
            results.append({'name': 'hardware_tools_required', 'status': 'PASS' if ok else 'FAIL',
                            'note': 'Tool presence is not proof of an AI inference workload'})
    statuses = [r['status'] for r in results]
    code = 1 if any(s in ('FAIL', 'TIMEOUT') for s in statuses) else 2 if 'SKIP' in statuses else 0
    report = {'title': 'MTA r208 unattended certification', 'started_utc': started,
              'finished_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'environment': os_info,
              'profile': args.profile, 'exit_code': code, 'checks': results,
              'not_certified_automatically': [
                'Actual GPU inference, GPU accounting, performance and billing settlement',
                'Crash/restart on a live server including SQLite/ledger/filesystem boundaries',
                'Native GUI behavior and installers on Windows/macOS/Linux',
                'GitHub Actions remote CI execution and deployment',
              ]}
    (out/'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    lines = ['# MTA r208 unattended verification', '', f'Platform: {platform.platform()}',
             f'Profile: {args.profile}', '', '| Check | Result |', '|---|---|']
    lines.extend(f"| {r['name']} | {r['status']} |" for r in results)
    lines += ['', '## Not certified by this runner', '']
    lines.extend('- '+x for x in report['not_certified_automatically'])
    (out/'report.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(f'FINAL STATUS: {"PASS" if code == 0 else "INCOMPLETE" if code == 2 else "FAIL"}; report: {out / "report.json"}')
    return code


if __name__ == '__main__':
    sys.exit(main())
