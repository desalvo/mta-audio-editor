"""Strict authenticated single-file ACM/STL evidence for defended chargebacks.

Only S6 plus an exact completed settlement credit can resolve a payout hold.
Other states/formats are refusals, not estimates or administrator waivers.
"""
import csv
from datetime import datetime, timezone
import hashlib
import io
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import tempfile
from .service_admission import operation

MAX_BYTES = 16*1024*1024
MAX_ROWS = 10000


class TransportUncertain(RuntimeError):
    """Child quiescence could not be established; retain original admission."""


def owned_call(source, call, *args, **kwargs):
    # This synchronous protocol owns every child and DB/HTTP context. Ordinary
    # failures have no surviving work; unknown child cleanup must retain C2.
    failure = None
    with operation(source):
        try:
            result = call(*args, **kwargs)
        except TransportUncertain:
            raise
        except Exception as exc:
            failure = exc
    if failure is not None:
        raise failure
    return result


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _private(path):
    path = Path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or info.st_nlink != 1 or info.st_mode & 0o077 or not 0 < info.st_size <= 128*1024):
            raise ValueError('Private report credentials required')
        raw = os.read(fd, 128*1024+1)
        if len(raw) != info.st_size:
            raise ValueError('Private report credentials changed')
        return raw
    finally:
        os.close(fd)


def fetch(username, key_file, known_hosts, acm_name, stl_name):
    return owned_call('paypal-report-download',_fetch,username,key_file,known_hosts,acm_name,stl_name)


def _fetch(username, key_file, known_hosts, acm_name, stl_name):
    """Fixed PayPal host, pinned host keys, no shell/config/agent/password fallback."""
    if os.name != 'posix' or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,99}', username):
        raise ValueError('Unsupported report transport')
    if (not re.fullmatch(r'ACM-\d{8}\.01\.\d{3}\.(?:CSV|csv)', acm_name)
            or not re.fullmatch(r'STL-\d{8}\.01\.\d{3}\.(?:CSV|csv)', stl_name)):
        raise ValueError('Exact single-file report names required')
    for name in [acm_name, stl_name]:
        datetime.strptime(name.split('-')[1].split('.')[0], '%Y%m%d')
    for binary in ['/usr/bin/sftp', '/usr/bin/ssh']:
        info = Path(binary).stat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError('Trusted OpenSSH installation required')
    key_bytes, host_bytes = _private(key_file), _private(known_hosts)
    identities = (digest(key_bytes), digest(host_bytes))
    import resource
    def limits():
        resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_BYTES, MAX_BYTES))
    with tempfile.TemporaryDirectory(prefix='mta-paypal-reports-') as folder:
        # SSH reads pinned private copies, not mutable operator paths after a
        # check. Neither credential bytes nor their copies enter a receipt.
        key, hosts = Path(folder)/'key', Path(folder)/'known_hosts'
        for path, raw in [(key,key_bytes),(hosts,host_bytes)]:
            path.write_bytes(raw); path.chmod(0o600)
        targets = [Path(folder)/'acm.csv', Path(folder)/'stl.csv']
        def quoted(path):
            value=str(path)
            if any(c in value for c in ['\n','\r','\0']):
                raise ValueError('Unsafe local report directory')
            return '"'+value.replace('\\','\\\\').replace('"','\\"')+'"'
        batch = f'get /disputes/outgoing/{acm_name} {quoted(targets[0])}\nget /ppreports/outgoing/{stl_name} {quoted(targets[1])}\n'
        command = ['/usr/bin/sftp', '-F', '/dev/null', '-S', '/usr/bin/ssh', '-q', '-b', '-',
                   '-oBatchMode=yes', '-oStrictHostKeyChecking=yes', '-oIdentitiesOnly=yes',
                   '-oPreferredAuthentications=publickey', '-oPasswordAuthentication=no',
                   '-oKbdInteractiveAuthentication=no', '-oGSSAPIAuthentication=no',
                   '-oControlMaster=no', '-oControlPath=none',
                   '-oIdentityAgent=none', '-oProxyCommand=none', '-oGlobalKnownHostsFile=/dev/null',
                   '-oUserKnownHostsFile='+str(hosts), '-oConnectTimeout=15', '-i', str(key),
                   username+'@reports.paypal.com']
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, start_new_session=True, preexec_fn=limits)
        try:
            process.communicate(batch.encode(), timeout=90)
            if process.returncode:
                raise ValueError('Authenticated report retrieval unavailable')
        finally:
            try:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=15)
            except Exception:
                raise TransportUncertain('Report child quiescence is unknown;retain original admission') from None
        if identities != (digest(_private(key_file)), digest(_private(known_hosts))):
            raise ValueError('Report credentials changed during retrieval')
        if any(p.is_symlink() or not p.is_file() or not 0 < p.stat().st_size <= MAX_BYTES for p in targets):
            raise ValueError('Incomplete report retrieval')
        raw = [p.read_bytes() for p in targets]
    return raw, {'host': 'reports.paypal.com', 'known_hosts_sha256': identities[1],
                 'acm_file': acm_name, 'stl_file': stl_name,
                 'acm_sha256': digest(raw[0]), 'stl_sha256': digest(raw[1])}


def _amount(value):
    if not isinstance(value, str) or not re.fullmatch('[0-9]{1,26}', value):
        raise ValueError('Exact report minor-unit amount required')
    return int(value)


def parse(raw, account, kind):
    """Subset: one account, one complete CSV file, named columns and exact totals."""
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES or b'\0' in raw:
        raise ValueError('Bounded UTF8 report required')
    records = []
    for row in csv.reader(io.StringIO(raw.decode('utf-8-sig')), strict=True):
        if len(records) >= MAX_ROWS+10 or not row or len(row)>100 or any(len(x)>4096 for x in row):
            raise ValueError('Report shape exceeds reviewed bounds')
        records.append(row)
    types = [r[0] for r in records]
    count = types.count('SB')
    prefix = ['RH','FH','SH','CH']+['SB']*count
    if types not in [prefix+['SF','SC','RF','RC','FF'], prefix+['SC','SF','RC','RF','FF']]:
        raise ValueError('Complete single-file report required')
    rh, fh, sh, columns = records[:4]
    if len(rh)==6 and rh[-1]=='':
        rh=rh[:-1]  # PayPal's documented ACM example has one trailing field.
    if (len(rh) != 5 or len(sh) != 5 or rh[3] != account or sh[3] != account
            or len(fh) != 2 or _amount(fh[1]) != 1 or len(columns) != len(set(columns))):
        raise ValueError('Original account/report identity mismatch')
    if rh[4] not in {'002','003','004','005','006'}:
        raise ValueError('Unsupported report version')
    footers={r[0]:r for r in records[4+count:]}
    if any(len(footers[k]) != 2 or _amount(footers[k][1]) != count for k in ['SC','RC','FF']):
        raise ValueError('Report row counts changed')
    fmt = '%m/%d/%Y %H:%M:%S %z' if kind == 'acm' else '%Y/%m/%d %H:%M:%S %z'
    start, end = datetime.strptime(sh[1], fmt), datetime.strptime(sh[2], fmt)
    if not start < end <= datetime.now(timezone.utc):
        raise ValueError('Invalid report interval')
    rows = []
    for values in records[4:4+count]:
        if len(values) != len(columns):
            raise ValueError('Report columns changed')
        rows.append(dict(zip(columns, values)))
    if kind == 'acm':
        if footers['SF'] != ['SF',str(count)]:
            raise ValueError('Unsupported case section footer')
        if len(footers['RF']) != 2 or _amount(footers['RF'][1]) != count:
            raise ValueError('Case report total mismatch')
    else:
        # Only EUR is currently admissible. Validate all principal/fee totals;
        # a report's statement totals do not themselves authorize any credit.
        footer = footers['RF']
        if len(footer) != 19 or footer[1] != 'EUR' or _amount(footer[18]) != count:
            raise ValueError('Settlement report total missing')
        if footers['SF'] != ['SF']+footer[1:]:
            raise ValueError('Settlement section totals changed')
        for index, prefix, direction in [(2,'gross','CR'),(3,'gross','DR'),(4,'fee','CR'),(5,'fee','DR')]:
            total = 0
            for row in rows:
                if row['gross_transaction_currency'] != 'EUR':
                    raise ValueError('Unsupported settlement currency')
                if row['fee_currency'] not in {'','EUR'}:
                    raise ValueError('Unsupported settlement fee currency')
                value = row['gross_transaction_amount' if prefix=='gross' else 'fee_amount']
                flag = row[prefix+'_debit_or_credit']
                if value == '' and prefix == 'fee' and flag == '':
                    continue
                if flag not in {'CR','DR'}:
                    raise ValueError('Invalid report direction')
                if flag == direction:
                    total += _amount(value)
            if total != _amount(footer[index]):
                raise ValueError('Settlement report principal/fee total mismatch')
    return rows, (start, end)


def defended(acm, stl, account):
    cases, case_window = parse(acm, account, 'acm')
    money, money_window = parse(stl, account, 'stl')
    if case_window != money_window:
        raise ValueError('Original case/settlement interval mismatch')
    result = {}; used = set()
    for row in cases:
        if row['Dispute Status'] != 'S6':
            continue
        cid, did, mid = (row[k] for k in ['Original Transaction ID','Dispute Case ID','Dispute Transaction ID'])
        if (not re.fullmatch('[A-Z0-9]{6,64}', cid) or not re.fullmatch('[A-Za-z0-9-]{1,100}', did)
                or not re.fullmatch('[A-Z0-9]{6,64}', mid) or (did,cid) in result or mid in used):
            raise ValueError('Ambiguous case/movement allocation')
        hits = [x for x in money if x['transaction_id'] == mid]
        amount = _amount(row['Disputed Gross Amount'])
        if (len(hits) != 1 or amount <= 0 or row['Disputed Gross Currency'] != 'EUR'
                or row['Disputed Gross Debit or Credit'] != 'CR' or row['Original Gross Currency'] != 'EUR'
                or row['Original Gross Debit or Credit'] != 'CR'):
            raise ValueError('Exact completed seller credit required')
        hit = hits[0]
        completed = datetime.strptime(hit['transaction_completion_date'], '%Y/%m/%d %H:%M:%S %z')
        filed = datetime.strptime(row['Dispute Filing Date'], '%Y%m%d %H:%M:%S %z')
        if (hit['paypal_reference_id'] != cid or hit['paypal_reference_id_type'] != 'TXN'
                or hit['transaction_event_code'] not in {'T1202','T1205'}
                or hit['gross_debit_or_credit'] != 'CR' or _amount(hit['gross_transaction_amount']) != amount
                or not money_window[0] <= completed <= money_window[1] or completed < filed):
            raise ValueError('Settlement does not bind exact original capture')
        used.add(mid)
        result[(did,cid)] = {'amount_minor': amount, 'capture_gross_minor': _amount(row['Original Gross Amount']),
                            'movement_id': mid, 'completed_at': completed.isoformat(),
                            'event_code': hit['transaction_event_code'], 'case_filed_at':filed.isoformat(),
                            'report_end':money_window[1].isoformat()}
    return result
