"""Real API preflight and fail-closed subprocess diagnostics without a browser."""
import json
from types import SimpleNamespace
import subprocess

import pytest
from app import auth
from test_r210_subscriptions import account as account  # noqa: F401
from test_r210_paypal import provider as provider  # noqa: F401
from test_r210_paypal_merchant_history import reporting as reporting  # noqa: F401
from test_r210_paypal_merchant_history_browser import merchant_panel_client as merchant_panel_client  # noqa: F401
from test_r210_merchant_chromium_gate import gate


def test_real_admin_panel_initial_reads_have_complete_empty_schema(merchant_panel_client,reporting):
    for path in (
        '/api/admin/service-regime',
        '/api/admin/service-regime/combined-readiness?target=NON_COMMERCIAL',
        '/api/admin/service-regime/payment-outbox-review?limit=25&offset=0',
        '/api/admin/service-regime/transition-reservations',
        '/api/admin/service-regime/payment-ledger?limit=50',
        '/api/admin/paypal/merchant-history?offset=0&limit=10',
    ):
        result=merchant_panel_client.get(path)
        assert result.status_code==200,(path,result.text)
    assert not reporting[1]
    with auth.db() as connection:
        assert connection.execute('SELECT count(*) FROM regime_payment_outbox').fetchone()[0]==0
        assert connection.execute('SELECT count(*) FROM paypal_orders').fetchone()[0]==0


@pytest.mark.parametrize('failure',['exit','timeout'])
def test_runner_keeps_diagnostics_and_rejects_stale_pass(tmp_path,monkeypatch,capsys,failure):
    (tmp_path/'pytest.xml').write_text('<testsuite/>')
    (tmp_path/'acceptance.json').write_text('{"accepted":true}')
    def run(command,**kwargs):
        assert not (tmp_path/'pytest.xml').exists()
        assert kwargs['env']['MTA_TEST_OFFLINE']=='1'
        kwargs['stdout'].write('x'*25_000+'\nREAL FAILURE DETAIL\n')
        kwargs['stdout'].flush()
        if failure=='timeout':
            raise subprocess.TimeoutExpired(command,kwargs['timeout'])
        return SimpleNamespace(returncode=1)
    monkeypatch.setattr(gate.subprocess,'run',run)
    assert gate.main(['--output',str(tmp_path)])==1
    assert json.loads((tmp_path/'acceptance.json').read_text())['accepted'] is False
    captured=capsys.readouterr().err
    assert 'REAL FAILURE DETAIL' in captured and len(captured)<21_000
    assert 'REAL FAILURE DETAIL' in (tmp_path/'pytest.log').read_text()
