"""Read-only, fail-closed operator readiness report for offline SQLite snapshots.

Usage: python -m app.regime_readiness_cli --db /path/to/snapshot.sqlite \
    --current NON_COMMERCIAL --target COMMERCIAL [--output report.json]

Never opens a writable connection or authorizes a transition.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import json
import os
import sqlite3
import stat
import sys
from pathlib import Path

from .regime_reconciliation import combined_readiness


def inspect_snapshot(path: str, *, current: str, target: str) -> dict:
    """Inspect an existing local DB without creating files or changing its schema."""
    if current not in ('COMMERCIAL', 'NON_COMMERCIAL') or target not in ('COMMERCIAL', 'NON_COMMERCIAL'):
        raise ValueError('Invalid regime')
    db = Path(path)
    if db.is_symlink() or not db.is_file():
        raise ValueError('Database must be an existing regular non-symlink file')
    # Reject replacement with a different file between validation and SQLite open.
    before = db.stat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError('Database must be a regular file')
    # URI quoting is handled by pathlib; mode=ro prevents accidental creation.
    uri = db.resolve().as_uri() + '?mode=ro'
    with closing(sqlite3.connect(uri, uri=True, timeout=3)) as connection:
        after = db.stat()
        if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino) or db.is_symlink():
            raise ValueError('Database changed during inspection')
        connection.execute('PRAGMA query_only=ON')
        connection.execute('PRAGMA busy_timeout=3000')
        try:
            report = combined_readiness(connection, current=current, target=target)
        except (sqlite3.DatabaseError, ValueError, KeyError) as exc:
            report = {'current': current, 'target': target,
                      'ready_for_automatic_transition': False,
                      'unresolved': ['readiness_inspection_failed'],
                      'error_type': type(exc).__name__}
    # Offline reports are diagnostic only, irrespective of apparent counters.
    report['ready_for_automatic_transition'] = False
    report['offline_snapshot_only'] = True
    report['diagnostic_only'] = True
    report['snapshot_file_identity'] = {'size_bytes': before.st_size}
    report['authorization_scope'] = 'none'
    report['requires_authenticated_provider_and_distributed_quiescence'] = True
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True, help='Existing local SQLite database/snapshot')
    parser.add_argument('--current', required=True, choices=['NON_COMMERCIAL','COMMERCIAL'])
    parser.add_argument('--target', required=True, choices=['NON_COMMERCIAL','COMMERCIAL'])
    parser.add_argument('--output', help='Write JSON report to a new file (never overwrite)')
    args = parser.parse_args(argv)
    try:
        report = inspect_snapshot(args.db, current=args.current, target=args.target)
        payload = json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False) + '\n'
        if args.output:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            if hasattr(os, 'O_NOFOLLOW'):
                flags |= os.O_NOFOLLOW
            fd = os.open(args.output, flags, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8') as output:
                output.write(payload)
        else:
            sys.stdout.write(payload)
    except (OSError, ValueError, sqlite3.DatabaseError) as exc:
        print(f'READINESS_BLOCKED: {type(exc).__name__}: {exc}', file=sys.stderr)
        return 2
    return 1  # No offline snapshot can certify live cutover.


if __name__ == '__main__':
    sys.exit(main())
