"""Offline immutable-snapshot window audit; never financial/account clearance."""
import argparse
import json
from pathlib import Path
import re
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import paypal_merchant_history as history  # noqa: E402


def audit(c, start, end, environment, fingerprint):
    left, right = history.instant(start), history.instant(end)
    if left >= right or environment not in {'sandbox', 'live'} or not re.fullmatch('[a-f0-9]{64}', fingerprint):
        raise ValueError('Exact nonempty UTC range and merchant identity required')
    intervals = []; seen = {}; conflicts = set(); ids = []
    for row in c.execute('SELECT * FROM paypal_merchant_history ORDER BY start_date,end_date,id'):
        # Validate every persisted row before filtering: corruption cannot be
        # hidden by its altered merchant/environment/window metadata.
        history.verify_snapshot(row)
        data = json.loads(row['evidence_json'])
        history.validate_observations(data)
        if history.digest(data) != row['evidence_sha256']:
            raise ValueError('Merchant evidence digest mismatch')
        if (row['environment'], row['merchant_fingerprint']) != (environment, fingerprint):
            continue
        a, b = history.instant(row['start_date']), history.instant(row['end_date'])
        if b <= left or a >= right:
            continue
        key = (row['start_date'], row['end_date'])
        if key in seen and seen[key] != row['evidence_sha256']:
            conflicts.add(key)
        seen[key] = row['evidence_sha256']
        intervals.append((max(a, left), min(b, right))); ids.append(row['id'])
    cursor = left; gaps = []
    for a, b in sorted(intervals):
        if a > cursor:
            gaps.append((cursor, a))
        cursor = max(cursor, b)
    if cursor < right:
        gaps.append((cursor, right))
    def stamp(value): return value.isoformat().replace('+00:00', 'Z')
    body = {'schema': 'mta-merchant-window-coverage-1', 'start_date': start, 'end_date': end,
            'environment': environment, 'merchant_fingerprint': fingerprint,
            'snapshot_ids': sorted(ids), 'gaps': [{'start_date': stamp(a), 'end_date': stamp(b)} for a, b in gaps],
            'conflicting_windows': [list(key) for key in sorted(conflicts)],
            'requested_window_covered': bool(intervals) and not gaps and not conflicts,
            'complete_account_history': False, 'ledger_reconciled': False,
            'transition_authorized': False, 'release_candidate': False,
            'scope': 'Persisted stable observations only;no freshness,provider availability or settlement proof'}
    return {**body, 'review_sha256': history.digest(body)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    for name in ['start', 'end', 'environment', 'fingerprint']:
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args()
    # mode=ro prevents even accidental creation; query_only protects the audit.
    try:
        with sqlite3.connect(args.database.resolve().as_uri()+'?mode=ro', uri=True) as c:
            c.row_factory = sqlite3.Row
            c.execute('PRAGMA query_only=ON'); c.execute('BEGIN')
            result = audit(c, args.start, args.end, args.environment, args.fingerprint)
        print(json.dumps(result, sort_keys=True))
        return 0 if result['requested_window_covered'] else 2
    except (OSError, ValueError, TypeError, KeyError, sqlite3.DatabaseError):
        print('Merchant coverage unavailable;original evidence must be retained', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
