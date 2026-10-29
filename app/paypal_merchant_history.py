"""Stable bounded merchant-wide PayPal observations, never cash/rights authority.

Fixed GET reporting queries; no customer details or payer-controlled labels stored.
A repeated transaction ID is not a unique movement or a case/capture allocation.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
import time
from urllib.parse import urlencode

from . import auth, paypal_payments as paypal
from .regime_operation_fence import FenceBlocked

MAX_PAGES = 20
MAX_ROWS = 2000


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


def instant(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', value):
        raise ValueError('UTC date/time with seconds required')
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def initialize(c):
    c.execute('''CREATE TABLE IF NOT EXISTS paypal_merchant_history(
      id TEXT PRIMARY KEY,environment TEXT NOT NULL,merchant_fingerprint TEXT NOT NULL,
      start_date TEXT NOT NULL,end_date TEXT NOT NULL,evidence_json TEXT NOT NULL,
      evidence_sha256 TEXT NOT NULL,actor_id INTEGER NOT NULL,created_at INTEGER NOT NULL)''')
    c.execute('''CREATE TRIGGER IF NOT EXISTS paypal_merchant_history_immutable BEFORE UPDATE ON paypal_merchant_history
      BEGIN SELECT RAISE(ABORT,'Immutable merchant history snapshot'); END''')


def _admin(c, actor):
    row = c.execute('SELECT role,active FROM users WHERE id=?', (actor,)).fetchone()
    if not row or tuple(row) != ('admin', 1):
        raise PermissionError('Active administrator required')


def _text(value, pattern, name):
    if not isinstance(value, str) or not re.fullmatch(pattern, value):
        raise ValueError('Invalid reporting '+name)
    return value


def normalize(row):
    if not isinstance(row, dict) or not isinstance(row.get('transaction_info'), dict):
        raise ValueError('Reporting transaction information required')
    item = row['transaction_info']
    result = {'transaction_id': _text(item.get('transaction_id'), r'[A-Za-z0-9-]{1,64}', 'identity'),
              'event_code': _text(item.get('transaction_event_code'), r'T[0-9]{4}', 'event code'),
              'status': _text(item.get('transaction_status'), r'[DPSV]', 'status')}
    for key in ('paypal_reference_id', 'paypal_reference_id_type', 'paypal_account_id'):
        value = item.get(key)
        if value is not None:
            result[key] = _text(value, r'[A-Za-z0-9-]{1,64}', key)
    amount = item.get('transaction_amount')
    if not isinstance(amount, dict):
        raise ValueError('Reporting amount required')
    result['currency'] = _text(amount.get('currency_code'), r'[A-Z]{3}', 'currency')
    result['amount'] = _text(amount.get('value'), r'-?[0-9]{1,20}(?:\.[0-9]{1,9})?', 'amount')
    # No fee/subject/note/email/name/cart/address enters persisted observations.
    for key in ('transaction_initiation_date', 'transaction_updated_date'):
        value = item.get(key)
        if value is not None:
            _text(value, r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|[+-]\d{2}:\d{2})', key)
            datetime.fromisoformat(value.replace('Z', '+00:00'))
            result[key] = value
    return result


def collect(cfg, start, end):
    page, pages, total = 1, None, None
    rows = {}
    while page <= MAX_PAGES:
        query = {'start_date': start, 'end_date': end, 'fields': 'transaction_info',
                 'balance_affecting_records_only': 'N', 'page_size': 100, 'page': page}
        response = paypal._api(cfg, 'GET', '/v1/reporting/transactions?' + urlencode(query))
        if not isinstance(response, dict):
            raise ValueError('Incomplete reporting response')
        data = response.get('transaction_details')
        p, n, count = response.get('page'), response.get('total_pages'), response.get('total_items')
        if (type(p) is not int or p != page or type(n) is not int or not 0 <= n <= MAX_PAGES
                or type(count) is not int or not 0 <= count <= MAX_ROWS
                or not isinstance(data, list) or len(data) > 100
                or (n == 0 and (count or data)) or (n > 0 and page > n)):
            raise ValueError('Invalid reporting pagination')
        if n != ((count+99)//100 if count else n) or (not count and n not in (0,1)):
            raise ValueError('Reporting page count does not match row count')
        if pages is None:
            pages, total = n, count
        elif (pages, total) != (n, count):
            raise ValueError('Reporting collection changed during paging')
        for raw in data:
            value = normalize(raw)
            key = digest(value)
            if key in rows:
                raise ValueError('Duplicate reporting row; coverage cannot be established')
            rows[key] = value
        if len(rows) > MAX_ROWS:
            raise ValueError('Reporting collection exceeds bound')
        if n == 0 or page == n:
            if len(rows) != total:
                raise ValueError('Incomplete reporting row count')
            return [rows[key] for key in sorted(rows)]
        if len(data) != 100:
            raise ValueError('Incomplete reporting page')
        page += 1
    raise ValueError('Reporting page bound exceeded')


def acquire(actor, start_date, end_date, *, confirm=False, expected_merchant=None):
    if confirm is not True:
        raise ValueError('Explicit merchant history confirmation required')
    start, end = instant(start_date), instant(end_date)
    if not timedelta(0) < end-start <= timedelta(days=31) or end > datetime.now(timezone.utc):
        raise ValueError('Past reporting range of at most31 days required')
    with auth.db() as c:
        paypal.init(c)
        _admin(c, actor)
        cfg = paypal._keys(c)
    if not cfg['enabled'] or not cfg['client_id'] or not cfg['client_secret']:
        raise ValueError('Configured merchant reporting access required')
    if expected_merchant is not None and expected_merchant != (
            cfg['environment'], hashlib.sha256(cfg['client_id'].encode()).hexdigest()):
        raise FenceBlocked('Original requested merchant changed before readback')
    first = collect(cfg, start_date, end_date)
    second = collect(cfg, start_date, end_date)
    if first != second:
        raise FenceBlocked('Merchant history changed; no snapshot accepted')
    evidence = encode(first)
    sha = hashlib.sha256(evidence.encode()).hexdigest()
    fingerprint = hashlib.sha256(cfg['client_id'].encode()).hexdigest()
    identity = digest([cfg['environment'], fingerprint, start_date, end_date, sha])
    with auth.db() as c:
        c.execute('BEGIN IMMEDIATE')
        _admin(c, actor)
        if paypal._keys(c) != cfg:
            raise FenceBlocked('Merchant configuration changed during readback')
        initialize(c)
        if not c.execute('SELECT 1 FROM paypal_merchant_history WHERE id=?', (identity,)).fetchone():
            count, stored = c.execute('SELECT count(*),coalesce(sum(length(evidence_json)),0) FROM paypal_merchant_history').fetchone()
            if count >= 120 or stored + len(evidence.encode()) > 32*1024*1024:
                raise FenceBlocked('Merchant history storage bound reached')
            c.execute('INSERT INTO paypal_merchant_history VALUES(?,?,?,?,?,?,?,?,?)',
                      (identity,cfg['environment'],fingerprint,start_date,end_date,evidence,sha,actor,int(time.time())))
    return {'snapshot_id': identity, 'records': len(first), 'stable_observation': True,
            'scope': 'requested_merchant_window_only', 'settlement_proven': False, 'transition_authorized': False}


def snapshots(actor, *, offset=0, limit=10):
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 20:
        raise ValueError('Invalid history pagination')
    with auth.db() as c:
        _admin(c, actor)
        exists = c.execute("SELECT 1 FROM sqlite_master WHERE name='paypal_merchant_history'").fetchone()
        if not exists:
            return {'items': [], 'total': 0, 'settlement_proven': False}
        rows = c.execute('SELECT * FROM paypal_merchant_history ORDER BY created_at DESC,id LIMIT ? OFFSET ?', (limit,offset)).fetchall()
        result = []
        for row in rows:
            verify_snapshot(row)
            data = json.loads(row['evidence_json'])
            if not isinstance(data,list) or len(data)>MAX_ROWS or digest(data)!=row['evidence_sha256']:
                raise FenceBlocked('Merchant history integrity failed')
            validate_observations(data)
            # Revalidate the persisted fixed DTO. Never render unknown JSON keys.
            for item in data:
                allowed = {'transaction_id','event_code','status','paypal_reference_id','paypal_reference_id_type',
                           'paypal_account_id','currency','amount','transaction_initiation_date','transaction_updated_date'}
                if not isinstance(item,dict) or set(item)-allowed:
                    raise FenceBlocked('Merchant history fields changed')
            result.append({key: row[key] for key in ('id','environment','start_date','end_date','created_at','actor_id')} |
                          {'records':len(data),'observations':data[:50],'truncated':len(data)>50,'settlement_proven':False})
        return {'items':result, 'total':c.execute('SELECT count(*) FROM paypal_merchant_history').fetchone()[0],
                'settlement_proven':False, 'scope':'stable_requested_windows_not_complete_account_history'}


def details(actor, snapshot_id, *, offset=0, limit=50):
    if not isinstance(snapshot_id,str) or not re.fullmatch(r'[a-f0-9]{64}',snapshot_id):
        raise ValueError('Exact merchant snapshot identifier required')
    if type(offset) is not int or offset<0 or type(limit) is not int or not 1<=limit<=100:
        raise ValueError('Invalid observation pagination')
    with auth.db() as c:
        _admin(c,actor)
        if not c.execute("SELECT 1 FROM sqlite_master WHERE name='paypal_merchant_history'").fetchone():
            raise ValueError('Unknown merchant snapshot')
        row=c.execute('SELECT * FROM paypal_merchant_history WHERE id=?',(snapshot_id,)).fetchone()
        if not row:
            raise ValueError('Unknown merchant snapshot')
        verify_snapshot(row)
        data=json.loads(row['evidence_json'])
        if not isinstance(data,list) or len(data)>MAX_ROWS or digest(data)!=row['evidence_sha256']:
            raise FenceBlocked('Merchant history integrity failed')
        validate_observations(data)
        return {'snapshot_id':snapshot_id,'items':data[offset:offset+limit],'total':len(data),
                'offset':offset,'settlement_proven':False}


def validate_observations(data):
    if not isinstance(data,list) or len(data)>MAX_ROWS:
        raise FenceBlocked('Merchant history collection changed')
    for item in data:
        try:
            raw={key:item[key] for key in ('paypal_reference_id','paypal_reference_id_type','paypal_account_id',
                 'transaction_initiation_date','transaction_updated_date') if key in item}
            raw.update(transaction_id=item['transaction_id'],transaction_event_code=item['event_code'],
                       transaction_status=item['status'],transaction_amount={'currency_code':item['currency'],'value':item['amount']})
            if normalize({'transaction_info':raw})!=item:
                raise ValueError('Changed observation fields')
        except (ValueError,TypeError,KeyError) as exc:
            raise FenceBlocked('Merchant history observation changed') from exc
    return data


def verify_snapshot(row):
    if (row['environment'] not in ('sandbox','live')
            or not re.fullmatch(r'[a-f0-9]{64}',row['merchant_fingerprint'])
            or row['id']!=digest([row['environment'],row['merchant_fingerprint'],row['start_date'],row['end_date'],row['evidence_sha256']])):
        raise FenceBlocked('Merchant snapshot identity changed')
    if not timedelta(0)<instant(row['end_date'])-instant(row['start_date'])<=timedelta(days=31):
        raise FenceBlocked('Merchant snapshot window changed')
