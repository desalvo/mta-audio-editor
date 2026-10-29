import hashlib
from datetime import timedelta

import pytest
from app import auth,paypal_payments as paypal,paypal_merchant_history as h
from scripts.acquire_merchant_range import acquire_next
from test_r210_subscriptions import account as account  # noqa: F401
from test_r210_paypal import provider as provider  # noqa: F401
from test_r210_paypal_merchant_history import reporting as reporting  # noqa: F401

F=hashlib.sha256(b'test-client').hexdigest()
START,END='2026-07-01T00:00:00Z','2026-09-15T00:00:00Z'


def run(reporting, **kw):
    return acquire_next(reporting[0], START, END, 'sandbox', F, confirm=True, **kw)


def test_actual_resumable_range_covers_three_windows_and_replays_without_network(reporting):
    reporting[2].clear()
    results=[run(reporting) for _ in range(3)]
    assert [r['resume_required'] for r in results]==[True,True,False]
    assert len(reporting[1])==6
    for query in reporting[1]:
        assert h.instant(query['end_date'][0])-h.instant(query['start_date'][0])<=timedelta(days=31)
    before=len(reporting[1]);last=run(reporting)
    assert last['acquired_snapshot'] is None and not last['resume_required']
    assert len(reporting[1])==before
    assert not any(last[k] for k in ['complete_account_history','ledger_reconciled','transition_authorized'])
    with auth.db() as c:assert c.execute('SELECT count(*) FROM paypal_orders').fetchone()[0]==0


def test_existing_middle_window_is_reused_not_downloaded_again(reporting):
    reporting[2].clear()
    h.acquire(reporting[0],'2026-08-01T00:00:00Z','2026-09-01T00:00:00Z',confirm=True)
    assert run(reporting)['resume_required']
    assert not run(reporting)['resume_required']
    assert len(reporting[1])==6


@pytest.mark.parametrize('defect',['confirm','actor','merchant','future','empty'])
def test_invalid_or_unconfirmed_range_never_contacts_provider(reporting,account,defect):
    actor=account if defect=='actor' else reporting[0]
    with pytest.raises((ValueError,PermissionError)):
        acquire_next(actor,END if defect=='empty' else START,'2099-01-01T00:00:00Z' if defect=='future' else END,
                     'sandbox','b'*64 if defect=='merchant' else F,confirm=defect!='confirm')
    assert not reporting[1]


def test_provider_failure_preserves_completed_window_then_resumes_gap(reporting,monkeypatch):
    reporting[2].clear();run(reporting);original=paypal._api
    def fail(*args):raise ValueError('provider unavailable')
    monkeypatch.setattr(paypal,'_api',fail)
    with pytest.raises(ValueError):run(reporting)
    with auth.db() as c:assert c.execute('SELECT count(*) FROM paypal_merchant_history').fetchone()[0]==1
    monkeypatch.setattr(paypal,'_api',original)
    run(reporting);assert not run(reporting)['resume_required']


def test_expected_merchant_is_checked_inside_original_acquisition_before_network(reporting):
    with pytest.raises(h.FenceBlocked):
        h.acquire(reporting[0],START,'2026-07-02T00:00:00Z',confirm=True,expected_merchant=('live',F))
    assert not reporting[1]
