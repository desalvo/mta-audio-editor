"""Tests that a real permitted model replaces blocked defaults, never forced requests."""
import pytest
import json
from model_rights_fixtures import synthetic_review
from app import model_license_policy as p


def test_primary_falls_back_to_licensed_mega53(monkeypatch, tmp_path):
    monkeypatch.setattr(p, '_path', lambda: tmp_path/'policy.json')
    monkeypatch.delenv('MTA_LEAD_BACKING_DEFAULT_MODEL', raising=False)
    assert p.effective_backing_model({}) == 'mvsep-mega53'
    assert p.evaluate('backing-vocals', {}).model_id == 'mvsep-mega53'
    assert p.evaluate('backing-vocals', {}).billable


def test_approved_primary_wins(monkeypatch, tmp_path):
    monkeypatch.setattr(p, '_path', lambda: tmp_path/'policy.json')
    monkeypatch.delenv('MTA_LEAD_BACKING_DEFAULT_MODEL', raising=False)
    (tmp_path/'policy.json').write_text(json.dumps({'uvr-kara-2':synthetic_review('free_only')}))
    assert p.effective_backing_model({}) == 'uvr_mdxnet_kara_2'
    assert not p.evaluate('backing-vocals', {}).billable


def test_explicit_blocked_primary_never_bypasses_license(monkeypatch, tmp_path):
    monkeypatch.setattr(p, '_path', lambda: tmp_path/'policy.json')
    assert p.effective_backing_model({'model':'uvr_mdxnet_kara_2'}) == 'uvr_mdxnet_kara_2'
    with pytest.raises(p.LicenseDenied):
        p.evaluate('backing-vocals', {'model':'uvr_mdxnet_kara_2'})


def test_fallback_respects_mega53_operator_disable(monkeypatch, tmp_path):
    monkeypatch.setattr(p, '_path', lambda: tmp_path/'policy.json')
    (tmp_path/'policy.json').write_text('{"mvsep-mega53":{"mode":"disabled"}}')
    with pytest.raises(p.LicenseDenied):
        p.evaluate('backing-vocals', {})


def test_explicit_drumsep_dsp_works_but_onnx_stays_blocked(monkeypatch, tmp_path):
    monkeypatch.setattr(p, '_path', lambda: tmp_path/'policy.json')
    assert p.evaluate('drumsep', {'model':'dsp'}).model_id == 'mta-analysis'
    with pytest.raises(p.LicenseDenied):
        p.evaluate('drumsep', {'model':'drumsep-onnx'})
