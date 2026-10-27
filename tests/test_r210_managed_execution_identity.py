"""Synthetic managed bytes + actual pull journal/ledger/process boundaries.

This certifies portable admission identity, not a loaded real neural checkpoint.
"""
import hashlib
import io
import json
import zipfile

import pytest

from app import model_license_policy as rights, studio_asset_registry as assets
from app import ai_pull_coordinator as central, ai_pull_worker as worker
from app.regime_operation_fence import FenceBlocked
from test_r208_unified_adapter_billing_e2e import operator as operator, source_audio  # noqa: F401
from test_r210_pull_coordinator import authority as authority, DirectClient, economic, task  # noqa: F401

PLAN={'options':{'asset_id':'identity-piano'}}
KIND='audio-to-midi-transkun'


def install_at(root, monkeypatch, *, checkpoint=b'synthetic piano A', runtime=b'# synthetic adapter\n'):
    from app import studio_catalog
    monkeypatch.setattr(studio_catalog,'root',lambda:root)
    files={'runtime/model.pt':checkpoint,'runtime/config.json':b'{}',
           'runtime/adapter.py':runtime,'LICENSE.txt':b'Synthetic fixture permission'}
    value={'schema':'mta-studio-bundle-1','id':'identity-piano','name':'Synthetic piano',
           'kind':'transkun','languages':['en'],
           'files':{name:{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()} for name,data in files.items()},
           'bindings':{'runtime_root':'runtime','checkpoint':'runtime/model.pt','config':'runtime/config.json'},
           'components':{'engine':'transkun-assets','checkpoint':'transkun-assets'},
           'component_files':{'engine':['runtime/config.json','runtime/adapter.py'],
                              'checkpoint':['runtime/model.pt']},
           'licenses':[{'policy_model':'transkun-assets','notice':'LICENSE.txt','evidence_url':'https://example.test/synthetic'}]}
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w') as archive:
        archive.writestr('manifest.json',json.dumps(value))
        for name,payload in files.items():archive.writestr(name,payload)
    assets.install(data.getvalue())
    rights.configure('transkun-assets',{'mode':'free_only','acknowledge_responsibility':True,
        'evidence_url':'https://example.test/synthetic','reason':'Synthetic test permission only',
        'free_access_confirmed':True,'authorization_basis':'written_permission','confirm_risk_twice':True},1)
    assets.configure('identity-piano',True)
    return root/'managed/identity-piano'


@pytest.fixture
def installed(tmp_path,monkeypatch):
    return install_at(tmp_path/'assets',monkeypatch)


def test_identity_is_portable_and_retains_unchanged_unmanaged_policy(installed,tmp_path,monkeypatch):
    first=rights.evaluate(KIND,PLAN)
    base=rights.evaluate('whisper',{})
    assert base==rights.evaluate_model('whisper')
    install_at(tmp_path/'second-host',monkeypatch)
    assert rights.evaluate(KIND,PLAN)==first
    assert first.mode=='free_only' and not first.billable


@pytest.mark.parametrize('change',['checkpoint','runtime','config','notice','added-file','link','directory-link','hardlink','disabled'])
def test_changed_installation_rejected_before_admission(installed,monkeypatch,change):
    if change in ('checkpoint','runtime','config','notice'):
        name={'checkpoint':'runtime/model.pt','runtime':'runtime/adapter.py','config':'runtime/config.json','notice':'LICENSE.txt'}[change]
        (installed/name).write_bytes(b'changed')
    elif change=='added-file':(installed/'runtime/other.pt').write_bytes(b'unknown')
    elif change=='link':(installed/'runtime/other.pt').symlink_to(installed/'runtime/model.pt')
    elif change=='directory-link':(installed/'runtime/extra').symlink_to(installed/'runtime',target_is_directory=True)
    elif change=='hardlink':
        import os
        os.link(installed/'runtime/model.pt',installed.parent/'alias')
    else:assets.configure('identity-piano',False)
    with pytest.raises((ValueError,OSError)):rights.evaluate(KIND,PLAN)


def setup_pull(authority,monkeypatch):
    # A separately authenticated registered node supports the synthetic engine.
    registration=central.register('managed-node',[KIND])
    monkeypatch.setenv('MTA_AI_WORKER_AUDIO_TO_MIDI_TRANSKUN_EXECUTABLE',str(authority[2]/'fixed_worker.py'))
    return registration


def test_authority_rejects_changed_inventory_before_dispatch(authority,monkeypatch):
    folder=install_at(authority[2]/'assets',monkeypatch)
    node=setup_pull(authority,monkeypatch)
    job=central.enqueue(authority[0],KIND,PLAN,source_wav=source_audio())
    before=task(job)['policy_json']
    # Complete, independently valid replacement under the same asset ID.
    install_at(authority[2]/'replacement',monkeypatch,checkpoint=b'synthetic piano B')
    with pytest.raises(FenceBlocked,match='policy changed'):
        central.assignment(node['credential'],'a'*32)
    assert task(job)['state']=='queued' and task(job)['policy_json']==before
    assert not (folder/'execution-count').exists()
    assert not (authority[2]/'execution-count').exists()


@pytest.mark.parametrize('difference',['checkpoint','runtime','same'])
def test_worker_compares_real_installed_identity_and_never_reexecutes(authority,monkeypatch,difference):
    from app import studio_catalog
    authority_root=authority[2]/'authority-assets'
    node_root=authority[2]/'node-assets'
    install_at(authority_root,monkeypatch)
    admitted=rights.evaluate(KIND,PLAN)
    node=setup_pull(authority,monkeypatch)
    job=central.enqueue(authority[0],KIND,PLAN,source_wav=source_audio())
    install_at(node_root,monkeypatch,
               checkpoint=b'synthetic piano B' if difference=='checkpoint' else b'synthetic piano A',
               runtime=b'# synthetic changed adapter\n' if difference=='runtime' else b'# synthetic adapter\n')
    class NodeClient(DirectClient):
        def call(self,*args,**kwargs):
            with monkeypatch.context() as context:
                context.setattr(studio_catalog,'root',lambda:authority_root)
                return super().call(*args,**kwargs)
    client=NodeClient(node['credential'])
    state=authority[2]/'worker-state'
    assert worker.run_once(client,state)
    assert task(job)['policy_json']==central.encode(__import__('dataclasses').asdict(admitted))
    assert json.loads((state/'active.json').read_text())['phase']=='done'
    if difference=='same':
        assert economic(job)==('done','finished','closed')
        assert (authority[2]/'execution-count').read_bytes()==b'1'
        assert not worker.run_once(client,state)
        assert (authority[2]/'execution-count').read_bytes()==b'1'
    else:
        assert economic(job)==('failed','finished','closed')
        assert central.recover(job)[1]['usage']=={}
        assert not (authority[2]/'execution-count').exists()
        assert not worker.run_once(client,state)


def test_old_policy_snapshot_is_not_silently_upgraded(authority,monkeypatch):
    install_at(authority[2]/'assets',monkeypatch)
    node=setup_pull(authority,monkeypatch)
    previous=rights.evaluate_model('transkun-assets')
    digest=hashlib.sha256((previous.policy_sha256*2).encode()).hexdigest()
    from dataclasses import replace
    # Admit using the actual previous decision shape; immutable DB guards stay on.
    with monkeypatch.context() as context:
        context.setattr(rights,'evaluate',lambda *_:replace(previous,policy_sha256=digest))
        job=central.enqueue(authority[0],KIND,PLAN,source_wav=source_audio())
    with pytest.raises(FenceBlocked,match='policy changed'):central.assignment(node['credential'],'b'*32)
    assert task(job)['state']=='queued'


def test_verified_digest_reused_but_same_size_write_with_restored_mtime_is_rejected(installed):
    import os
    rights.evaluate(KIND,PLAN)
    hits=assets._verified_digest.cache_info().hits
    rights.evaluate(KIND,PLAN)
    assert assets._verified_digest.cache_info().hits>hits
    target=installed/'runtime/model.pt';before=target.stat()
    target.write_bytes(b'X'*before.st_size)
    os.utime(target,ns=(before.st_atime_ns,before.st_mtime_ns))
    with pytest.raises(ValueError,match='checksum'):rights.evaluate(KIND,PLAN)
