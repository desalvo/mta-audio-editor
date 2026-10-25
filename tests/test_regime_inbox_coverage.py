import sqlite3
from app.regime_inbox_coverage import audit_provider_inbox
from app.regime_operation_fence import initialize


def make_db():
    c=sqlite3.connect(':memory:')
    initialize(c)
    c.execute('''CREATE TABLE regime_provider_inbox (
      provider TEXT, event_id TEXT, operation_id TEXT, payload_sha256 TEXT, state TEXT)''')
    return c


def test_missing_schema_fails_closed():
    assert audit_provider_inbox(sqlite3.connect(':memory:'))['verified'] is False


def test_empty_inbox_is_locally_consistent_not_transition_certified():
    c=make_db()
    result=audit_provider_inbox(c)
    assert result['verified'] and result['pending']==0 and not result['transition_safe']


def test_unprocessed_event_is_blocker():
    c=make_db()
    c.execute("INSERT INTO regime_fence_operations VALUES ('checkout:1','checkout','COMMERCIAL',0,'open')")
    c.execute('INSERT INTO regime_provider_inbox VALUES (?,?,?,?,?)',('stripe','evt1','checkout:1','a'*64,'received'))
    result=audit_provider_inbox(c)
    assert result['verified'] and result['pending']==1


def test_orphan_and_bad_digest_detected():
    c=make_db()
    c.execute('INSERT INTO regime_provider_inbox VALUES (?,?,?,?,?)',('paypal','evt2','missing','not-a-hash','applied'))
    result=audit_provider_inbox(c)
    assert not result['verified']
    assert result['inconsistencies']['orphan_provider_event']==1


def test_applied_valid_event_is_locally_consistent():
    c=make_db()
    c.execute("INSERT INTO regime_fence_operations VALUES ('checkout:1','checkout','COMMERCIAL',0,'closed')")
    c.execute('INSERT INTO regime_provider_inbox VALUES (?,?,?,?,?)',('paypal','evt3','checkout:1','b'*64,'applied'))
    result=audit_provider_inbox(c)
    assert result['verified'] and result['pending']==0


def test_duplicate_provider_event_identity_blocks_readiness():
    c=make_db()
    c.execute("INSERT INTO regime_fence_operations VALUES ('checkout:1','checkout','COMMERCIAL',0,'open')")
    for digest in ('a'*64, 'b'*64):
        c.execute('INSERT INTO regime_provider_inbox VALUES (?,?,?,?,?)',
                  ('stripe','evt1','checkout:1',digest,'applied'))
    result=audit_provider_inbox(c)
    assert result['verified'] is False
    assert result['inconsistencies']['duplicate_event_identity']==1

def test_empty_event_identity_and_negative_epoch_are_rejected():
    c=make_db()
    c.execute("INSERT INTO regime_fence_operations VALUES ('checkout:1','checkout','COMMERCIAL',-1,'open')")
    c.execute('INSERT INTO regime_provider_inbox VALUES (?,?,?,?,?)',
              ('stripe','  ','checkout:1','a'*64,'applied'))
    result=audit_provider_inbox(c)
    assert not result['verified']
    assert result['inconsistencies']['invalid_event_identity']==1
