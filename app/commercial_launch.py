"""Pre-commercial launch boundary; no migration of earlier monetary books.

The persistent, non-personal marker survives account erasure. It records that
commercial checkout began, not that a provider collected or refunded money.
"""
from .regime_operation_fence import FenceBlocked

PROFILE='precommercial-no-payment-history-1'
TABLE='regime_commercial_origin'
SCHEMA=('''CREATE TABLE IF NOT EXISTS regime_commercial_origin(
        singleton INTEGER PRIMARY KEY CHECK(singleton=1),revision INTEGER NOT NULL CHECK(revision>=0))''',
    '''CREATE TRIGGER IF NOT EXISTS regime_commercial_origin_no_update
        BEFORE UPDATE ON regime_commercial_origin BEGIN SELECT RAISE(ABORT,'Immutable commercial origin'); END''',
    '''CREATE TRIGGER IF NOT EXISTS regime_commercial_origin_no_delete
        BEFORE DELETE ON regime_commercial_origin BEGIN SELECT RAISE(ABORT,'Immutable commercial origin'); END''')


def _validate(c):
    names=(TABLE,TABLE+'_no_update',TABLE+'_no_delete')
    for name,expected in zip(names,SCHEMA):
        row=c.execute('SELECT sql FROM sqlite_master WHERE name=?',(name,)).fetchone()
        def normalized(value):return ''.join(value.upper().split()).replace('IFNOTEXISTS','')
        if row is None or normalized(row[0])!=normalized(expected):
            raise FenceBlocked('Original commercial origin schema unavailable')


def mark_started(c):
    if not c.in_transaction:raise FenceBlocked('Commercial launch marker requires checkout transaction')
    exists=c.execute("SELECT 1 FROM sqlite_master WHERE name=?",(TABLE,)).fetchone()
    if exists:_validate(c)
    else:
        for sql in SCHEMA:c.execute(sql)
    row=c.execute("SELECT revision FROM regime_fence_state WHERE singleton=1 AND regime='COMMERCIAL' AND transitioning=0").fetchone()
    if row is None:raise FenceBlocked('Original open commercial epoch required')
    c.execute('INSERT OR IGNORE INTO regime_commercial_origin VALUES(1,?)',(row[0],))


def require_not_started(c):
    exists=c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(TABLE,)).fetchone()
    if exists:_validate(c)
    if exists and c.execute('SELECT 1 FROM regime_commercial_origin LIMIT 1').fetchone():
        raise FenceBlocked('Commercial checkout has started; automatic financial history migration is not supported')
