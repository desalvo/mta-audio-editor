"""Public active-regime legal terms regression tests."""
import hashlib
from pathlib import Path
import pytest
from fastapi import HTTPException
from app import resource_routes, service_regime

@pytest.mark.parametrize('mode', [service_regime.Regime.NON_COMMERCIAL, service_regime.Regime.COMMERCIAL])
@pytest.mark.parametrize('lang', ['it','en'])
def test_terms_selected_and_hashed(monkeypatch, mode, lang):
    monkeypatch.setattr(service_regime, 'current_regime', lambda: mode)
    result = resource_routes.public_regime_terms(lang)
    assert result['regime'] == mode.value
    assert result['language'] == lang
    assert len(result['text']) > 800
    assert result['sha256'] == hashlib.sha256(result['text'].encode()).hexdigest()
    assert result['legal_review_required'] is True

def test_terms_reject_unknown_language():
    with pytest.raises(HTTPException) as exc:
        resource_routes.public_regime_terms('../en')
    assert exc.value.status_code == 422


def test_about_links_to_terms():
    js = (Path(__file__).resolve().parents[1] / 'app/static/app.js').read_text()
    assert 'Regolamento del servizio' in js[js.index('async function showAbout()'):js.index('function openExportPanel()')]


def test_public_terms_html_escapes_and_preserves_lang(monkeypatch):
    monkeypatch.setattr(service_regime, 'current_regime', lambda: service_regime.Regime.NON_COMMERCIAL)
    doc = resource_routes.service_terms_document('it')
    assert b'Regolamento del servizio' in doc.body
    assert b'NON_COMMERCIAL' in doc.body
    assert b'<article>' in doc.body
    with pytest.raises(HTTPException):
        resource_routes.service_terms_document('fr')
