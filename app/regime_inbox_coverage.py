"""Read-only reconciliation of authenticated payment events against checkout admissions.

A clean local inbox is necessary but not sufficient for changing service regime:
external provider settlement and remote workers still require independent proof.
"""
from __future__ import annotations

import sqlite3

from .regime_operation_fence import FenceBlocked


def audit_provider_inbox(connection: sqlite3.Connection) -> dict:
    """Fail closed on missing schemas, orphan events and unprocessed webhook records."""
    tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    required = {'regime_provider_inbox', 'regime_fence_operations'}
    if not required.issubset(tables):
        return {'verified': False, 'pending': None,
                'inconsistencies': {'missing_tables': len(required - tables)},
                'transition_safe': False}
    try:
        problems = dict(connection.execute('''
          SELECT reason, COUNT(*) FROM (
            SELECT CASE
              WHEN f.operation_id IS NULL THEN 'orphan_provider_event'
              WHEN i.event_id IS NULL OR trim(i.event_id) = '' THEN 'invalid_event_identity'
              WHEN f.revision IS NULL OR f.revision < 0 THEN 'invalid_checkout_epoch'
              WHEN f.kind!='checkout' OR f.regime!='COMMERCIAL' THEN 'invalid_checkout_receipt'
              WHEN i.provider NOT IN ('stripe','paypal') THEN 'unknown_provider'
              WHEN i.state NOT IN ('received','applied') THEN 'invalid_event_state'
              WHEN length(i.payload_sha256)!=64 OR i.payload_sha256 GLOB '*[^0-9a-f]*'
                THEN 'invalid_payload_digest'
              ELSE NULL END AS reason
            FROM regime_provider_inbox i
            LEFT JOIN regime_fence_operations f ON f.operation_id=i.operation_id
          ) WHERE reason IS NOT NULL GROUP BY reason
        '''))
        # Legacy inbox schemas can lack the newer (provider,event_id) key.
        # Even on those databases, repeated IDs must not be considered clean.
        duplicates = connection.execute("""SELECT COUNT(*) FROM (
            SELECT provider,event_id FROM regime_provider_inbox
            GROUP BY provider,event_id HAVING COUNT(*) > 1
        )""").fetchone()[0]
        if duplicates:
            problems['duplicate_event_identity'] = duplicates
        pending = connection.execute("SELECT COUNT(*) FROM regime_provider_inbox WHERE state!='applied'").fetchone()[0]
    except sqlite3.DatabaseError as exc:
        raise FenceBlocked('Cannot audit provider inbox') from exc
    return {'verified': not problems, 'pending': pending,
            'inconsistencies': problems, 'transition_safe': False}
