"""Fail-closed checkpoint acquisition and durable operator review tests."""
import json
import pytest
from app import model_license_policy as policy
from app import chord_ml


def test_chordformer_download_denied_before_network(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR',str(tmp_path))
    def no_download(*args,**kwargs):
        raise AssertionError('network download must not be reached')
    monkeypatch.setattr(chord_ml,'_download_zip',no_download)
    with pytest.raises(policy.LicenseDenied):
        chord_ml.download_model('chordformer')


def test_history_preserves_prior_attestations(tmp_path,monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR',str(tmp_path))
    def body(mode,why):
        return {'mode':mode,'acknowledge_responsibility':True,
                'evidence_url':'https://example.org/explicit-written-authorization',
                'reason':why,'free_access_confirmed':True,'confirm_risk_twice':True,'authorization_basis':'written_permission'}
    policy.configure('drumsep-weights',body('free_only','Rights verified for exact checkpoint; free service'),7)
    policy.configure('drumsep-weights',body('disabled','Rights withdrawn; stop new admissions immediately'),8)
    with pytest.raises(policy.LicenseDenied):policy.evaluate_model('drumsep-weights')
    history=json.loads(policy._path().with_name('license-policy-history.json').read_text())
    assert len(history)==2
    assert history[0]['review']['actor_id']==7
    assert history[1]['previous']['mode']=='free_only'
    assert history[1]['review']['actor_id']==8


def test_unknown_models_fail_closed(tmp_path,monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR',str(tmp_path))
    for name in ('future-ai-v42','audio-separator-weights','drumsep-weights','madmom','chordformer'):
        with pytest.raises(policy.LicenseDenied):policy.evaluate_model(name)
