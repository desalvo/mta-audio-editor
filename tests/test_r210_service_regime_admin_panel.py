"""Regression contract for fail-closed bilingual regime admin UI."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_admin_template_embeds_panel():
    page = (ROOT / 'app/templates/admin.html').read_text()
    assert 'id="serviceRegimePanel"' in page
    assert '/static/regime_admin_panel.js?v=' in page


def test_panel_uses_admin_read_only_endpoints_and_no_switch():
    script = (ROOT / 'app/static/regime_admin_panel.js').read_text()
    assert '/api/admin/service-regime/combined-readiness' in script
    assert '/api/admin/service-regime/payment-outbox-review' in script
    assert '/api/admin/service-regime/transition-reservations' in script
    assert '/api/admin/service-regime/abort-transition-reservation' in script
    assert 'regime switching' in script.lower()
    assert 'credentials:\'same-origin\'' in script
    assert 'cache:\'no-store\'' in script
    assert 'innerHTML=JSON.stringify' not in script
    assert 'POST /api/admin/service-regime/switch' not in script


def test_admin_refresh_includes_regime():
    script = (ROOT / 'app/static/admin.js').read_text()
    assert 'window.mtaRefreshServiceRegime?.()' in script


def test_panel_bilingual_and_recovery_checks():
    script = (ROOT / 'app/static/regime_admin_panel.js').read_text()
    assert 'it:{' in script and 'en:{' in script
    assert 'reservations.integrity_verified!==true' in script
    assert 'reservations.transitioning!==true' in script
    assert 'expected_revision:item.revision' in script
    assert "'X-MTA-Request':'1'" in script
