"""Offline release-candidate acceptance gate for MTA 0.3.0-r210.

An isolated SQLite snapshot cannot prove external provider or distributed-worker
readiness. Missing independently verified evidence ALWAYS blocks promotion.
This command neither changes production state nor creates a Git release.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .regime_readiness_cli import inspect_snapshot

_REQUIRED = (
    'stripe_authenticated_sandbox_reconciliation',
    'paypal_authenticated_sandbox_reconciliation',
    'webhook_retry_and_pending_inbox_e2e',
    'distributed_ai_workers_quiescence_e2e',
    'administrative_cutover_and_rollback_e2e',
    'commercial_noncommercial_billing_e2e',
    'ai_licensing_all_executors_e2e',
    'full_ci_regression',
)


def evaluate(*, db: str | None = None, current: str = 'NON_COMMERCIAL',
             target: str = 'COMMERCIAL', evidence: dict | None = None) -> dict:
    """Conservative machine-readable release blocking report.

    Evidence is informational, not authority: an offline report must never be
    treated as an authenticated financial/distributed attestation.
    """
    evidence = evidence if isinstance(evidence, dict) else {}
    checks = {}
    for key in _REQUIRED:
        item = evidence.get(key)
        checks[key] = {'status': 'unverified', 'provided': isinstance(item, dict),
                       'claimed_pass': isinstance(item, dict) and item.get('status') == 'passed',
                       'requires_independent_validation': True}
    report = None
    if db:
        try:
            report = inspect_snapshot(db, current=current, target=target)
        except (OSError, ValueError) as exc:
            report = {'ready_for_automatic_transition': False,
                      'unresolved': ['snapshot_inspection_failed'], 'error_type': type(exc).__name__}
    blockers = list(_REQUIRED)
    if report is None:
        blockers.append('database_readiness_not_supplied')
    else:
        blockers.extend(str(x) for x in report.get('unresolved', []))
        blockers.append('offline_snapshot_cannot_certify_live_readiness')
    return {'version': '0.3.0-r210', 'candidate': False, 'release_authorized': False,
            'cutover_authorized': False, 'status': 'BLOCKED',
            'checks': checks, 'database_diagnostic': report,
            'blockers': sorted(set(blockers)),
            'reason': 'Provider settlement and distributed execution require independent end-to-end verification'}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', help='Optional offline SQLite snapshot (read-only)')
    parser.add_argument('--current', choices=['NON_COMMERCIAL', 'COMMERCIAL'], default='NON_COMMERCIAL')
    parser.add_argument('--target', choices=['NON_COMMERCIAL', 'COMMERCIAL'], default='COMMERCIAL')
    parser.add_argument('--evidence', help='Optional JSON evidence index (not authoritative)')
    parser.add_argument('--output', help='New JSON report, exclusive create (never overwrite)')
    args = parser.parse_args(argv)
    try:
        evidence = json.loads(Path(args.evidence).read_text(encoding='utf-8')) if args.evidence else None
        report = evaluate(db=args.db, current=args.current, target=args.target, evidence=evidence)
        payload = json.dumps(report, indent=2, sort_keys=True) + '\n'
        if args.output:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)
            with os.fdopen(os.open(args.output, flags, 0o600), 'w', encoding='utf-8') as f:
                f.write(payload)
        else:
            sys.stdout.write(payload)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f'RC_GATE_ERROR: {type(exc).__name__}: {exc}', file=sys.stderr)
        return 2
    return 1


if __name__ == '__main__':
    sys.exit(main())
