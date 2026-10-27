"""Complete operator lifecycle readback; actual journal/receipts, no supplied readiness."""
import sqlite3

import pytest
from app import auth, regime_admin_cutover as cutover
from app.regime_transition_status import overview
from app.regime_operation_fence import FenceBlocked
from test_r210_admin_cutover_e2e import ready as ready, account as account, begin, BASE, HEADERS  # noqa: F401

PATH=BASE+'/lifecycle'


def reserve_actual(ready,identifier='progress-reservation'):
    from app.regime_transition_journal import reserve
    client,_,actor=ready
    preview=cutover.preview(actor=actor,target='NON_COMMERCIAL')
    with auth.db() as con:
        con.execute('BEGIN IMMEDIATE')
        proof=cutover.audit(con)
        reserve(con,transition_id=identifier,target=preview['target'],expected_revision=preview['source_revision'],
                evidence={'ready':True,'unresolved':[],'source':proof['profile']})
    return identifier


def committed_actual(ready,monkeypatch):
    original=cutover.reconcile_mirror
    def interrupted(*args):raise RuntimeError('isolated interrupted mirror')
    monkeypatch.setattr(cutover,'reconcile_mirror',interrupted)
    body=begin(ready[0],identifier='progress-committed')
    with pytest.raises(RuntimeError):ready[0].post(BASE,json=body,headers=HEADERS)
    monkeypatch.setattr(cutover,'reconcile_mirror',original)
    return body


def test_read_only_initial_status_has_real_counts_and_private_role_guard(ready):
    client,_,_=ready
    result=client.get(PATH);assert result.status_code==200
    assert result.headers['cache-control']=='no-store'
    data=result.json();assert data['phase']=='idle' and data['integrity_verified'] and not data['transition_authorized']
    with auth.db() as con:
        assert not con.execute("SELECT 1 FROM sqlite_master WHERE name='regime_reservation_aborts'").fetchone()
        assert con.execute('SELECT transitioning FROM regime_fence_state').fetchone()[0]==0
    for query in ('?limit=0','?limit=101','?offset=-1'):assert client.get(PATH+query).status_code==422


def test_reservation_abort_keeps_epoch_money_and_exact_actor_audit(ready):
    from app.regime_balance_continuity import snapshot
    client,_,actor=ready;identifier=reserve_actual(ready)
    with auth.db() as con:
        con.execute('BEGIN');before=snapshot(con)
    data=client.get(PATH).json();assert data['phase']=='reserved' and data['active']['action']=='abort_reservation'
    url=BASE+'/reservations/'+identifier+'/abort'
    assert client.post(url,json={'expected_revision':0,'confirm':True}).status_code==403
    for body in ({'confirm':True},{'expected_revision':0,'confirm':1},{'expected_revision':1,'confirm':True}):
        assert client.post(url,json=body,headers=HEADERS).status_code in (409,422)
    for _ in range(2):assert client.post(url,json={'expected_revision':0,'confirm':True},headers=HEADERS).status_code==200
    result=client.get(PATH).json();assert result['phase']=='idle' and result['items'][0]['phase']=='aborted'
    assert result['items'][0]['events'][0]['actor_id']==actor
    assert result['items'][0]['events'][0]['created_at']
    with auth.db() as con:
        con.execute('BEGIN');assert snapshot(con)==before
        assert con.execute('SELECT regime,revision,transitioning FROM regime_fence_state').fetchone()[:]==('COMMERCIAL',0,0)
        for query in ('DELETE FROM regime_reservation_aborts',"UPDATE regime_reservation_aborts SET actor_id=999"):
            with pytest.raises(sqlite3.IntegrityError):con.execute(query)

    body=begin(client,identifier='post-abort-cutover')
    assert client.post(BASE,json=body,headers=HEADERS).status_code==200


def test_committed_report_proves_original_receipts_and_only_forward_recovery(ready,monkeypatch):
    client=ready[0];body=committed_actual(ready,monkeypatch)
    data=client.get(PATH).json();assert data['phase']=='committed' and data['integrity_verified']
    assert data['active']['action']=='forward_recovery' and data['fence']['transitioning']
    assert client.post(BASE+'/reservations/'+body['request_id']+'/abort',json={'expected_revision':0,'confirm':True},headers=HEADERS).status_code==409
    assert client.post(BASE+'/'+body['request_id']+'/recover',json={'expected_revision':1,'confirm':True},headers=HEADERS).status_code==200
    data=client.get(PATH).json();assert data['phase']=='idle' and data['items'][0]['phase']=='finalized'
    assert [e['phase'] for e in data['items'][0]['events']]==['committed','finalized']


@pytest.mark.parametrize('damage',['balance','mirror','second_reservation','orphan_commit','wrong_epoch'])
def test_corruption_or_missing_evidence_never_offers_unsafe_recovery(ready,monkeypatch,damage):
    client,uid,_=ready;committed_actual(ready,monkeypatch)
    if damage=='mirror':(auth.data_root()/'service-regime.json').write_text('{"regime":"COMMERCIAL","revision":999}')
    else:
        with sqlite3.connect(auth.db_path()) as con:
            if damage=='balance':con.execute('UPDATE resource_credits SET delta_micro=1 WHERE user_id=?',(uid,))
            elif damage=='second_reservation':con.execute("INSERT INTO regime_transition_journal SELECT 'second-reservation',source_regime,target_regime,source_revision,evidence_sha256,status FROM regime_transition_journal")
            elif damage=='orphan_commit':con.execute("INSERT INTO regime_cutover_commits VALUES('orphan','COMMERCIAL','NON_COMMERCIAL',100,101)")
            else:con.execute('UPDATE regime_fence_state SET revision=999')
    data=client.get(PATH).json();assert data['phase'] in ('blocked','committed')
    assert data['active'] is None or data['active']['action'] is None
    assert data['reason'] and not data['transition_authorized']
    with auth.db() as con:assert con.execute('SELECT transitioning FROM regime_fence_state').fetchone()[0]==1


def test_tracked_open_work_is_visible_and_not_certified_as_total_service_drain(ready):
    client=ready[0];reserve_actual(ready)
    with auth.db() as con:con.execute("INSERT INTO regime_fence_operations VALUES('legacy-running','job','COMMERCIAL',0,'open')")
    data=client.get(PATH).json();assert data['fence']['open_by_kind']['job']==1
    assert not data['fence']['all_entry_points_instrumented']
    assert data['active']['action'] is None


def test_old_aborted_history_does_not_gain_invented_actor_and_pages_are_complete(ready):
    from app.regime_transition_journal import abort_verified
    client,_,_=ready;identifier=reserve_actual(ready)
    with auth.db() as con:
        con.execute('BEGIN IMMEDIATE');abort_verified(con,transition_id=identifier,expected_revision=0)
    data=client.get(PATH).json();assert data['items'][0]['events']==[] and not data['items'][0]['actor_evidence_available']
    assert client.post(BASE+'/reservations/'+identifier+'/abort',headers=HEADERS,json={'expected_revision':0,'confirm':True}).status_code==409
    for index in range(3):
        key=reserve_actual(ready,'new-reservation-'+str(index))
        assert client.post(BASE+'/reservations/'+key+'/abort',headers=HEADERS,json={'expected_revision':0,'confirm':True}).status_code==200
    pages=[client.get(PATH+'?limit=1&offset='+str(i)).json() for i in range(4)]
    assert len({page['items'][0]['id'] for page in pages})==4
    assert all(page['total']==4 for page in pages)


def test_legacy_commit_is_reported_without_adopting_admin_authority(ready):
    from app.regime_balance_continuity import commit_preserving_balances
    client=ready[0];identifier=reserve_actual(ready)
    with auth.db() as con:
        con.execute('BEGIN IMMEDIATE')
        commit_preserving_balances(con,transition_id=identifier,expected_revision=0,readiness_check=lambda c:bool(cutover.audit(c)))
    data=client.get(PATH).json();assert data['phase']=='committed'
    assert data['reason']=='legacy_commit_requires_maintenance' and data['active']['action'] is None
    assert client.post(BASE+'/'+identifier+'/recover',headers=HEADERS,json={'expected_revision':1,'confirm':True}).status_code==409


def test_active_admin_required_for_all_lifecycle_paths(ready,monkeypatch):
    from test_r210_owner_payments import client as login
    for uid,expected in [(None,401),(ready[1],403)]:
        web=login(uid,monkeypatch)
        assert web.get(PATH).status_code==expected
        assert web.post(BASE+'/reservations/any/abort',headers=HEADERS,json={'expected_revision':0,'confirm':True}).status_code==expected
    with pytest.raises(FenceBlocked):overview(actor=ready[1])


def test_recovery_settings_remain_accessible_after_commit(ready,monkeypatch):
    committed_actual(ready,monkeypatch)
    response=ready[0].get('/settings')
    assert response.status_code==200
    assert 'regime_cutover_panel.js' in response.text
