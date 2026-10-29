from dataclasses import dataclass
from pathlib import Path

import pytest

from app import ai_model_attestation as att
from app.ai_payload_limits import worker_artifact_bytes,validate_artifact_mib
from app.model_license_policy import Decision


def test_internal_pull_ceiling_does_not_change_public_configuration_minimum(monkeypatch):
    monkeypatch.setenv('MTA_AI_JOB_MAX_ARTIFACT_MIB','16')
    assert worker_artifact_bytes()==16*1024*1024
    with pytest.raises(ValueError):validate_artifact_mib(16)


@pytest.mark.parametrize('value',['0','15','17','63','016','16.0','-16','8193'])
def test_other_invalid_trusted_limits_remain_invalid(monkeypatch,value):
    monkeypatch.setenv('MTA_AI_JOB_MAX_ARTIFACT_MIB',value)
    with pytest.raises(ValueError):worker_artifact_bytes()


def test_installed_rights_document_is_checked_not_just_a_version_string(tmp_path,monkeypatch):
    import importlib.metadata
    @dataclass
    class Distribution:
        files:tuple=(Path('fixture.dist-info/LICENSE'),Path('fixture.dist-info/NOTICE'))
        def locate_file(self,path):return tmp_path/path
    folder=tmp_path/'fixture.dist-info';folder.mkdir()
    (folder/'LICENSE').write_text('unreviewed replacement');(folder/'NOTICE').write_text('unreviewed')
    monkeypatch.setattr(importlib.metadata,'version',lambda name:att.RIGHTS['runtime'][name])
    monkeypatch.setattr(importlib.metadata,'distribution',lambda name:Distribution())
    with pytest.raises(ValueError,match='rights evidence changed'):att.runtime_identity()


@pytest.mark.parametrize('field',['sources','rights','epoch'])
def test_worker_independently_refuses_a_substituted_contract(monkeypatch,field):
    monkeypatch.setenv('MTA_PULL_MODEL_ATTESTATION',att.VERIFIED_MODE)
    decision=Decision('basic-pitch','cost_recovery','https://example.test','a'*64)
    required=att.requirement('audio-to-midi-basic-pitch',decision)
    # Canonical transport serialization prevents mutation of the source registry.
    import json
    required=json.loads(json.dumps(required));required['epoch']={'regime':'COMMERCIAL','revision':0}
    if field=='sources':required['sources']['ai_model_bytes.py']='0'*64
    elif field=='rights':required['rights']['license']='invented grant'
    else:required['epoch']['revision']=True
    with pytest.raises(ValueError):att.verify_contract(required,decision)


def test_reviewed_profile_cannot_be_bypassed_by_generic_remote_transport(monkeypatch):
    from app.model_license_policy import authorize_remote_execution,LicenseDenied
    monkeypatch.setenv('MTA_PULL_MODEL_ATTESTATION',att.VERIFIED_MODE)
    with pytest.raises(LicenseDenied,match='authenticated pull checkpoint'):
        authorize_remote_execution('audio-to-midi-basic-pitch',{})
