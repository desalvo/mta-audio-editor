"""Original installed script/role/current component rights before opaque code."""
import hashlib
import io
import json
from pathlib import Path
import os
import subprocess
import sys
import zipfile

import pytest
from app import studio_asset_registry as assets,model_license_policy as policy
from model_rights_fixtures import offline_singing_fixture

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def installed(tmp_path,monkeypatch):
    from app import auth
    monkeypatch.setenv('MTA_DATA_DIR',str(tmp_path));monkeypatch.setattr(auth,'DATA_ROOT',None)
    marker=tmp_path/'executed'
    files={'runtime/infer.py':('from pathlib import Path\nPath('+repr(str(marker))+').write_text("once")\n').encode(),
           'model.pt':b'OWN SYNTHETIC BYTES','LICENSE.txt':b'Own fixture notice'}
    roles={'engine','acoustic','pitch_extractor','semantic_encoder','voice_authorization'}
    value={'schema':'mta-studio-bundle-1','id':'fixture-rvc','name':'Synthetic RVC contract',
        'kind':'rvc','languages':['en'],'files':{n:{'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()} for n,b in files.items()},
        'bindings':{'runtime_root':'runtime','script':'runtime/infer.py','checkpoint':'model.pt'},
        'components':{role:'rvc-assets' for role in roles},'component_files':{role:list(files) for role in roles},
        'licenses':[{'policy_model':'rvc-assets','notice':'LICENSE.txt','evidence_url':'https://example.org/own-generated-fixture'}]}
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as z:
        z.writestr('manifest.json',json.dumps(value))
        for n,b in files.items():z.writestr(n,b)
    assets.install(stream.getvalue())
    policy.configure('rvc-assets',{'mode':'cost_recovery','acknowledge_responsibility':True,
        'evidence_url':'https://example.org/own-generated-fixture','reason':'Only generated fixture bytes; not an actual installed checkpoint grant',
        'free_access_confirmed':False,'authorization_basis':'written_permission','confirm_risk_twice':True},1)
    assets.configure('fixture-rvc',True)
    manifest=assets.manifest('fixture-rvc',verify=True)
    env={**os.environ,'MTA_STUDIO_OFFLINE_KIND':'rvc','MTA_STUDIO_CONVERSION_ASSET_ID':'fixture-rvc'}
    return manifest,env,marker


def execute(script,environment,cwd):
    return subprocess.run([sys.executable,str(ROOT/'app/studio_offline_runner.py'),str(script)],env=environment,
                          cwd=cwd,capture_output=True,text=True,timeout=10,check=False)


def test_original_installed_component_executes_under_actual_child_policy(installed):
    value,environment,marker=installed
    result=execute(assets.binding(value,'script'),environment,assets.binding(value,'runtime_root'))
    assert result.returncode==0,result.stderr
    assert marker.read_text()=='once'


@pytest.mark.parametrize('defect',['role','missing_role','asset','foreign_script','changed_script','cwd','disabled','revoked','guard'])
def test_wrong_original_component_or_permission_never_executes(installed,tmp_path,defect):
    value,environment,marker=installed
    script=assets.binding(value,'script');cwd=assets.binding(value,'runtime_root')
    if defect=='role':environment['MTA_STUDIO_OFFLINE_KIND']='seed-vc'
    if defect=='missing_role':environment.pop('MTA_STUDIO_OFFLINE_KIND')
    if defect=='asset':environment['MTA_STUDIO_CONVERSION_ASSET_ID']='foreign-rvc'
    if defect=='foreign_script':
        script=tmp_path/'foreign.py';script.write_text('raise AssertionError("foreign must not run")')
    if defect=='changed_script':script.write_text('raise AssertionError("changed must not run")')
    if defect=='cwd':cwd=tmp_path
    if defect=='disabled':assets.configure('fixture-rvc',False)
    if defect=='revoked':
        path=policy._path();data=json.loads(path.read_text());data['rvc-assets']['mode']='disabled';path.write_text(json.dumps(data))
    if defect=='guard':
        # The Seed wrapper cannot silently downgrade to the RVC tensor contract.
        result=subprocess.run([sys.executable,str(ROOT/'app/seed_vc_runner.py'),str(script)],env=environment,
                              cwd=cwd,capture_output=True,text=True,timeout=10,check=False)
    else:result=execute(script,environment,cwd)
    assert result.returncode!=0 and not marker.exists(),result.stderr
    assert 'foreign must not run' not in result.stderr and 'changed must not run' not in result.stderr


@pytest.mark.parametrize('defect',['role','script','singer','vocoder','format'])
def test_actual_singing_child_cannot_be_used_as_generic_script_runner(tmp_path,defect):
    runtime,env=offline_singing_fixture(tmp_path);marker=tmp_path/'executed'
    script=runtime/'scripts/infer.py';script.write_text('from pathlib import Path\nPath('+repr(str(marker))+').write_text("bad")\n')
    if defect=='role':env.pop('MTA_STUDIO_OFFLINE_KIND')
    if defect=='script':
        script=tmp_path/'other.py';script.write_text('raise AssertionError("wrong script")')
    if defect in {'singer','vocoder'}:
        policy_file=tmp_path/'.studio-models/license-policy.json';data=json.loads(policy_file.read_text())
        data['diffsinger-nishiren' if defect=='singer' else 'diffsinger-vocoder']['mode']='disabled';policy_file.write_text(json.dumps(data))
    if defect=='format':env['MTA_DIFFSINGER_FORMAT']='unknown'
    result=execute(script,env,runtime)
    assert result.returncode!=0 and not marker.exists(),result.stderr
