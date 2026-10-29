"""Confirmed resumable PayPal range acquisition; no financial clearance."""
import argparse
from datetime import timedelta, datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import auth, paypal_payments as paypal, paypal_merchant_history as history  # noqa: E402
from scripts.audit_merchant_coverage import audit  # noqa: E402


def acquire_next(actor, start, end, environment, fingerprint, *, confirm=False):
    if confirm is not True:
        raise ValueError('Explicit original merchant range confirmation required')
    first, last = history.instant(start), history.instant(end)
    if first >= last or last > datetime.now(timezone.utc) or last-first > timedelta(days=1096):
        raise ValueError('Past nonempty range of at most1096 days required')
    with auth.db() as c:
        history._admin(c, actor)
        cfg = paypal._keys(c)
        if (cfg['environment'], hashlib.sha256(cfg['client_id'].encode()).hexdigest()) != (environment, fingerprint):
            raise ValueError('Explicit configured merchant identity required')
        history.initialize(c)
    with auth.db() as c:
        c.execute('BEGIN')
        history._admin(c, actor)
        state = audit(c, start, end, environment, fingerprint)
    if state['conflicting_windows']:
        raise ValueError('Conflicting original windows require review;no automatic replacement')
    if state['requested_window_covered']:
        return {**state, 'acquired_snapshot': None, 'resume_required': False}
    gap = state['gaps'][0]
    a = history.instant(gap['start_date'])
    b = min(history.instant(gap['end_date']), a+timedelta(days=31))
    stamp = lambda t: t.isoformat().replace('+00:00', 'Z')
    receipt = history.acquire(actor, stamp(a), stamp(b), confirm=True,
                              expected_merchant=(environment, fingerprint))
    with auth.db() as c:
        c.execute('BEGIN')
        history._admin(c, actor)
        if paypal._keys(c) != cfg:
            raise ValueError('Configuration changed;preserve original snapshots and review before resuming')
        state = audit(c, start, end, environment, fingerprint)
    return {**state, 'acquired_snapshot': receipt['snapshot_id'],
            'resume_required': not state['requested_window_covered']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--actor', type=int, required=True)
    for key in ['start', 'end', 'environment', 'fingerprint']:
        parser.add_argument('--'+key, required=True)
    parser.add_argument('--confirm', action='store_true')
    args = parser.parse_args()
    try:
        result = acquire_next(args.actor, args.start, args.end, args.environment, args.fingerprint, confirm=args.confirm)
        print(json.dumps(result, sort_keys=True))
        return 2 if result['resume_required'] else 0
    except Exception:
        # Provider errors and sealed configuration never enter terminal output.
        print('Range acquisition blocked;retain original snapshots and review configuration/evidence', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
