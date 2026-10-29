"""Authenticated report -> canonical case -> original ledger and replay."""
import copy
import csv
import io
import json
from pathlib import Path
import subprocess
import shlex
import os

import pytest
from app import auth,paypal_payments as paypal,resource_accounts as resources
from app import paypal_settlement_reports as reports,paypal_report_reconciliation as recovery
from app import payment_reconcile_service as service,payment_reconciliation as journal
from app.regime_operation_fence import FenceBlocked
from test_r210_subscriptions import account as account  # noqa: F401
from test_r210_paypal import provider as provider  # noqa: F401
from test_r210_paypal_dispute_history import fixture

ACCOUNT='MERCHANT123'
ACM='ACM-20261025.01.006.CSV'
STL='STL-20261025.01.006.CSV'


def documents(*,multi=False):
    cases=[];money=[]
    for i,(cid,amount,gross) in enumerate([('CAPTURE111',200,300)]+([('CAPTURE222',200,200)] if multi else [])):
        mid='MOVEMENT'+str(i+1)
        cases.append({'Dispute Status':'S6','Dispute Case ID':'PP-D-123','Original Transaction ID':cid,
            'Dispute Filing Date':'20261023 00:00:00 +0000',
            'Dispute Transaction ID':mid,'Disputed Gross Amount':str(amount),'Disputed Gross Currency':'EUR',
            'Disputed Gross Debit or Credit':'CR','Original Gross Amount':str(gross),
            'Original Gross Currency':'EUR','Original Gross Debit or Credit':'CR',
            'Claimant Name':'PRIVATE NAME','Claimant Email Address':'private@example.test'})
        money.append({'transaction_id':mid,'paypal_reference_id':cid,'paypal_reference_id_type':'TXN',
            'transaction_event_code':'T1202','gross_debit_or_credit':'CR','gross_transaction_amount':str(amount),
            'gross_transaction_currency':'EUR','fee_amount':'','fee_debit_or_credit':'','fee_currency':'',
            'transaction_completion_date':'2026/10/24 14:00:00 +0000'})
    return cases,money


def encode_rows(cases,money):
    def encode(rows,kind):
        start,end=(('10/24/2026 00:00:00 +0000','10/25/2026 00:00:00 +0000') if kind=='acm'
                   else ('2026/10/24 00:00:00 +0000','2026/10/25 00:00:00 +0000'))
        output=io.StringIO();writer=csv.writer(output)
        fields=list(rows[0])
        writer.writerows([['RH',end,'X',ACCOUNT,'006'],['FH','01'],['SH',start,end,ACCOUNT,''],['CH',*fields]])
        writer.writerows([['SB',*(row[k] for k in fields)] for row in rows])
        footer=(['RF',str(len(rows))] if kind=='acm' else
                ['RF','EUR',str(sum(int(r['gross_transaction_amount']) for r in rows)), '0','0','0',
                 'CR','0','CR','0','CR','0','CR','0','CR','0','CR','0',str(len(rows))])
        writer.writerows([['SF',str(len(rows))] if kind=='acm' else ['SF',*footer[1:]],['SC',str(len(rows))],
                          footer,['RC',str(len(rows))],['FF',str(len(rows))]])
        return output.getvalue().encode()
    return [encode(cases,'acm'),encode(money,'stl')]


@pytest.fixture
def ledger(account,provider,monkeypatch):
    local,order,docs,calls,hook=fixture(account,provider,monkeypatch,paid=True)
    order['purchase_units'][0]['payee']={'merchant_id':ACCOUNT}
    docs['PP-D-123'].update(status='RESOLVED',create_time='2026-10-23T00:00:00Z',dispute_outcome={'outcome_code':'RESOLVED_WITH_PAYOUT'})
    # The actual provider transport remains mocked. No live account is used.
    paypal.settings({'environment':'live'})
    with auth.db() as c:c.execute("UPDATE paypal_orders SET environment='live' WHERE id=?",(local,))
    service.reconcile_paypal(local)
    assert resources.state(account)['credits_micro']==3_000_000
    raw=encode_rows(*documents());provenance={'host':'reports.paypal.com','known_hosts_sha256':'a'*64,
        'acm_file':ACM,'stl_file':STL,'acm_sha256':reports.digest(raw[0]),'stl_sha256':reports.digest(raw[1])}
    monkeypatch.setattr(reports,'fetch',lambda *args:(raw,provenance))
    return {'local':local,'order':order,'docs':docs,'raw':raw,'calls':calls,'hook':hook,
            'admin':auth.find_user('admin')['id']}


def apply(ledger):
    return recovery.reconcile(ledger['admin'],ledger['local'],username='report-user',key_file='unused',
        known_hosts='unused',acm_name=ACM,stl_name=STL,confirm=True)


def test_exact_completed_defended_report_releases_original_hold_and_replays(ledger,account):
    result=apply(ledger)
    assert result['ledger_reconciled'] and not result['financial_review_pending']
    assert resources.state(account)['credits_micro']==5_000_000
    apply(ledger);service.reconcile_paypal(ledger['local'])
    assert resources.state(account)['credits_micro']==5_000_000
    with auth.db() as c:
        assert journal.report(c)['pending']==0
        events=[json.loads(r[0]) for r in c.execute("SELECT normalized_json FROM payment_reconciliation_events WHERE provider='paypal'")]
        proofs=[e['settlement_report_proof'] for e in events if 'settlement_report_proof' in e]
        assert len(proofs)==1 and proofs[0]['movement_id']=='MOVEMENT1'
        assert proofs[0]['actor_id']==ledger['admin']
        assert 'PRIVATE NAME' not in json.dumps(proofs) and 'private@example.test' not in json.dumps(proofs)


@pytest.mark.parametrize('defect',['account','amount','currency','reference','direction','fee_event','temporary_hold','duplicate',
    'case','capture','gross','status','not_resolved','changed_case','missing_payee','role','config','owner','report_timeout',
    'reused_case','stale_report'])
def test_invalid_or_changed_evidence_never_releases_original_money(ledger,account,monkeypatch,defect):
    cases,money=documents()
    if defect=='account':ledger['order']['purchase_units'][0]['payee']['merchant_id']='FOREIGN'
    if defect=='amount':cases[0]['Disputed Gross Amount']='100'
    if defect=='currency':cases[0]['Disputed Gross Currency']='USD'
    if defect=='reference':money[0]['paypal_reference_id']='CAPTURE222'
    if defect=='direction':cases[0]['Disputed Gross Debit or Credit']='DR'
    if defect=='fee_event':money[0]['transaction_event_code']='T0100'
    if defect=='temporary_hold':money[0]['transaction_event_code']='T1111'
    if defect=='duplicate':money.append(copy.deepcopy(money[0]))
    if defect=='case':cases[0]['Dispute Case ID']='FOREIGN-CASE'
    if defect=='capture':cases[0]['Original Transaction ID']='CAPTURE222'
    if defect=='gross':cases[0]['Original Gross Amount']='999'
    if defect=='status':cases[0]['Dispute Status']='S2'
    if defect=='not_resolved':ledger['docs']['PP-D-123']['status']='UNDER_REVIEW'
    if defect=='changed_case':ledger['docs']['PP-D-123']['dispute_amount']['value']='1.00'
    if defect=='reused_case':ledger['docs']['PP-D-123']['create_time']='2026-10-24T00:00:00Z'
    if defect=='stale_report':ledger['docs']['PP-D-123']['update_time']='2026-10-26T00:00:00Z'
    if defect=='missing_payee':ledger['order']['purchase_units'][0].pop('payee')
    ledger['raw'][:]=encode_rows(cases,money)
    if defect in {'role','config','owner'}:
        original=reports.fetch
        def fetch(*args):
            value=original(*args)
            with auth.db() as c:
                if defect=='role':c.execute('UPDATE users SET active=0 WHERE id=?',(ledger['admin'],))
                if defect=='config':c.execute("UPDATE paypal_config SET enabled=0")
                if defect=='owner':c.execute('UPDATE paypal_orders SET user_id=1 WHERE id=?',(ledger['local'],))
            return value
        monkeypatch.setattr(reports,'fetch',fetch)
    if defect=='report_timeout':monkeypatch.setattr(reports,'fetch',lambda *a:(_ for _ in ()).throw(ValueError('timeout')))
    try:apply(ledger)
    except (ValueError,FenceBlocked):pass
    assert resources.state(account)['credits_micro']<=3_000_000


def test_changed_canonical_after_resolution_is_pending_not_a_second_refund(ledger,account):
    apply(ledger)
    ledger['docs']['PP-D-123']['update_time']='2026-10-25T03:00:00Z'
    assert service.reconcile_paypal(ledger['local'])['financial_review_pending']
    assert resources.state(account)['credits_micro']==5_000_000


def test_failure_after_report_resolution_rolls_back_all_credit_changes(ledger,account,monkeypatch):
    original=paypal._apply_risk
    def fail(*args):original(*args);raise RuntimeError('injected before commit')
    monkeypatch.setattr(paypal,'_apply_risk',fail)
    with pytest.raises(RuntimeError):apply(ledger)
    assert resources.state(account)['credits_micro']==3_000_000
    monkeypatch.setattr(paypal,'_apply_risk',original);apply(ledger)
    assert resources.state(account)['credits_micro']==5_000_000


@pytest.mark.parametrize('mutation',['truncate','footer','duplicate_header','foreign_header','extra_section','bad_utf8','huge','nul'])
def test_incomplete_raw_report_cannot_become_authority(mutation):
    acm,stl=encode_rows(*documents())
    if mutation=='truncate':acm=acm[:acm.rfind(b'FF')]
    if mutation=='footer':acm=acm.replace(b'RF,1',b'RF,2')
    if mutation=='duplicate_header':acm=acm.replace(b'CH,Dispute Status',b'CH,Dispute Status,Dispute Status')
    if mutation=='foreign_header':acm=acm.replace(ACCOUNT.encode(),b'FOREIGN')
    if mutation=='extra_section':acm+=b'SH,x,y,z\n'
    if mutation=='bad_utf8':acm=b'\xff'
    if mutation=='huge':acm=b'a'*(reports.MAX_BYTES+1)
    if mutation=='nul':acm+=b'\0'
    with pytest.raises((ValueError,KeyError)):reports.defended(acm,stl,ACCOUNT)


def test_multicapture_report_allocates_each_distinct_completed_credit():
    data=reports.defended(*encode_rows(*documents(multi=True)),ACCOUNT)
    assert len(data)==2 and sum(p['amount_minor'] for p in data.values())==400


def test_same_provider_movement_cannot_be_adopted_by_a_second_case(ledger,account):
    apply(ledger)
    original=ledger['docs']['PP-D-123'];second=copy.deepcopy(original)
    second['dispute_id']='PP-D-SECOND';ledger['docs']['PP-D-SECOND']=second
    cases,money=documents();cases[0]['Dispute Case ID']='PP-D-SECOND'
    ledger['raw'][:]=encode_rows(cases,money)
    with pytest.raises(FenceBlocked,match='Financial event identity'):
        apply(ledger)
    assert resources.state(account)['credits_micro']==5_000_000


def test_documented_acm_footer_order_and_trailing_report_field_are_supported():
    acm,stl=encode_rows(*documents())
    rows=list(csv.reader(io.StringIO(acm.decode())));rows[0].append('')
    footer={r[0]:r for r in rows[-5:]}
    rows=rows[:-5]+[footer[k] for k in ['SC','SF','RC','RF','FF']]
    output=io.StringIO();csv.writer(output).writerows(rows)
    assert reports.defended(output.getvalue().encode(),stl,ACCOUNT)


@pytest.mark.parametrize('spaces',[False,True])
@pytest.mark.skipif(os.name!='posix' or not Path('/usr/bin/sftp').is_file(),reason='POSIX OpenSSH reporting target required')
def test_transport_is_fixed_host_pinned_keys_bounded_and_reaps(tmp_path,monkeypatch,spaces):
    key,hosts=tmp_path/'key',tmp_path/'hosts'
    for p in [key,hosts]:p.write_bytes(b'PRIVATE FIXTURE');p.chmod(0o600)
    observed={};raw=encode_rows(*documents())
    if spaces:
        folder=tmp_path/'space dir';folder.mkdir()
        monkeypatch.setattr(reports.tempfile,'tempdir',str(folder))
    class Process:
        pid=123456789;returncode=0
        def communicate(self,batch,timeout):
            observed['timeout']=timeout
            for line,data in zip(batch.decode().splitlines(),raw):Path(shlex.split(line)[-1]).write_bytes(data)
        def wait(self,timeout=None):observed['waited']=True
    def spawn(command,**kwargs):observed['command']=command;observed['kwargs']=kwargs;return Process()
    monkeypatch.setattr(reports.subprocess,'Popen',spawn)
    monkeypatch.setattr(reports.os,'killpg',lambda pid,sig:observed.update(killed=pid))
    received,source=reports.fetch('report-user',key,hosts,ACM,STL)
    assert received==raw and source['host']=='reports.paypal.com'
    command=observed['command']
    assert command[-1]=='report-user@reports.paypal.com' and '-oStrictHostKeyChecking=yes' in command
    assert '-oIdentityAgent=none' in command and '-oProxyCommand=none' in command
    assert observed['kwargs']['preexec_fn'] and observed['kwargs']['start_new_session']
    assert observed['waited'] and observed['killed']==123456789 and observed['timeout']==90


@pytest.mark.parametrize('defect',['username','path','format','key_mode','symlink','timeout'])
@pytest.mark.skipif(os.name!='posix' or not Path('/usr/bin/sftp').is_file(),reason='POSIX OpenSSH reporting target required')
def test_unsafe_transport_never_returns_unverified_report(tmp_path,monkeypatch,defect):
    key,hosts=tmp_path/'key',tmp_path/'hosts'
    for p in [key,hosts]:p.write_bytes(b'fixture');p.chmod(0o600)
    if defect=='key_mode':key.chmod(0o644)
    if defect=='symlink':key.unlink();key.symlink_to(hosts)
    class Process:
        pid=123456789
        def communicate(self,*a,**kw):raise subprocess.TimeoutExpired('sftp',90)
        def wait(self,timeout=None):pass
    monkeypatch.setattr(reports.subprocess,'Popen',lambda *a,**k:Process())
    monkeypatch.setattr(reports.os,'killpg',lambda *a:None)
    with pytest.raises((ValueError,OSError,subprocess.TimeoutExpired)):
        reports.fetch('user@evil' if defect=='username' else 'user',key,hosts,
            '../'+ACM if defect=='path' else ACM,STL.replace('CSV','TAB') if defect=='format' else STL)


@pytest.mark.skipif(os.name!='posix',reason='POSIX authority admission target required')
def test_actual_drain_waits_for_report_recovery_and_closes_after_reaped_work(ledger,account,monkeypatch):
    from app import service_admission as gate
    monkeypatch.setenv('MTA_SERVICE_ADMISSION',gate.MODE)
    original=reports.fetch
    def read(*args):
        value=original(*args)
        state=gate.inspect(actor=ledger['admin'])
        assert state['active_by_source']['paypal-report-recovery']==1
        state=gate.change(actor=ledger['admin'],expected_generation=0,draining=True,
                          identifier='report-drain-1',confirm=True)
        assert state['phase']=='draining' and not state['drained']
        return value
    monkeypatch.setattr(reports,'fetch',read)
    assert apply(ledger)['settlement_report_resolutions']==1
    assert gate.inspect(actor=ledger['admin'])['active_count']==0
    with gate.control():assert resources.state(account)['credits_micro']==5_000_000


@pytest.mark.parametrize('uncertain',[False,True])
@pytest.mark.skipif(os.name!='posix',reason='POSIX authority admission target required')
def test_admission_distinguishes_finished_failure_from_unknown_child(ledger,monkeypatch,uncertain):
    from app import service_admission as gate
    monkeypatch.setenv('MTA_SERVICE_ADMISSION',gate.MODE)
    error=reports.TransportUncertain('unknown') if uncertain else ValueError('finished failure')
    def fail(*args):raise error
    monkeypatch.setattr(reports,'fetch',fail)
    with pytest.raises(type(error)):apply(ledger)
    assert gate.inspect(actor=ledger['admin'])['active_count']==int(uncertain)
