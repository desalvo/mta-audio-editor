"""Fail-closed optional catalog, immutable sources and native/server installation."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest
from app import optional_plugins as p

ROOT=Path(__file__).resolve().parents[1]


def test_catalog_is_pinned_licensed_and_sorted():
    catalog=p.catalog()
    assert len(catalog['plugins'])==4
    assert catalog['plugins']==sorted(catalog['plugins'],key=lambda x:(x['category'],x['name']))
    for spec in catalog['plugins']:
        assert len(spec['revision'])==40 and spec['distribution']=='local-source-build'
        assert hashlib.sha256((p.LICENSES/spec['license_file']).read_bytes()).hexdigest()==spec['license_sha256']
    assert p.select(['mverb'])[0]['repo']=='DISTRHO/MVerb'


@pytest.mark.parametrize('ids',[[],['unknown'],['mverb','mverb'],['../../etc/passwd'],'mverb'])
def test_untrusted_selection_refused(ids):
    with pytest.raises(ValueError):p.select(ids)


def test_overdue_or_disabled_catalog_cannot_install(tmp_path,monkeypatch):
    path=tmp_path/'catalog.json';data=json.loads(p.CATALOG.read_text());data['reviewed_at']='2020-01-01';path.write_text(json.dumps(data));monkeypatch.setattr(p,'CATALOG',path)
    with pytest.raises(ValueError,match='review overdue'):p.select(['mverb'])
    data['reviewed_at']='2099-01-01';data['plugins'][0]['enabled']=False;path.write_text(json.dumps(data))
    with pytest.raises(ValueError):p.select(['mverb'])


def test_license_tampering_refuses_catalog(tmp_path,monkeypatch):
    path=tmp_path/'catalog.json';data=json.loads(p.CATALOG.read_text());data['plugins'][0]['license_sha256']='0'*64;path.write_text(json.dumps(data));monkeypatch.setattr(p,'CATALOG',path)
    with pytest.raises(ValueError,match='integrity'):p.catalog()


def test_builder_targets_vst3_only_and_handles_chow_subdirectory(tmp_path):
    for spec in p.catalog()['plugins']:
        commands=p.commands(spec,tmp_path/'source')
        assert all(isinstance(cmd,list) for cmd in commands)
        if spec['id']=='chow-tape':assert str(tmp_path/'source/Plugin') in commands[0] and 'CHOWTapeModel_VST3' in commands[-1]
        if spec['builder']=='dpf':assert commands[-1][-2:] == ['vst3','USE_FILE_BROWSER=false']


def test_install_publishes_atomically_after_verified_source_and_license(tmp_path,monkeypatch):
    from app import auth
    monkeypatch.setattr(auth,'DATA_ROOT',tmp_path/'data')
    monkeypatch.setenv('MTA_OPTIONAL_VST3_DIR',str(tmp_path/'installed'))
    spec=p.select(['mverb'])[0];calls=[]
    def run(command,cwd,log,notify,timeout=3600):
        calls.append(command)
        if command[0]=='make':
            assert not list((tmp_path/'installed').rglob('*.vst3'))
            binary=cwd/'bin/MVerb.vst3/Contents/x86_64-linux/MVerb.so';binary.parent.mkdir(parents=True,exist_ok=True);binary.write_bytes(b'test')
        if 'checkout' in command:(cwd/'LICENSE').write_bytes((p.LICENSES/spec['license_file']).read_bytes())
    monkeypatch.setattr(p,'_run',run)
    monkeypatch.setattr(p.subprocess,'run',lambda *a,**kw:subprocess.CompletedProcess(a,0,spec['revision']+'\n',''))
    result=p.install_one(spec)
    assert result['bundles']==['MVerb.vst3']
    installed=p.plugin_root()/'mverb'/spec['revision']
    assert (installed/'installation.json').is_file() and (installed/'MVerb.vst3/Contents/x86_64-linux/MVerb.so').read_bytes()==b'test'
    assert ['git','fetch','--depth','1','origin',spec['revision']] in calls


def test_periodic_check_uses_fixed_revision_and_reports_mismatch():
    spec=importlib.util.spec_from_file_location('optional_review',ROOT/'scripts/review_optional_vst3.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    data=p.catalog();urls=[]
    def download(url):
        urls.append(url);entry=next(x for x in data['plugins'] if x['repo'] in url)
        return (p.LICENSES/entry['license_file']).read_bytes()
    assert all(x['license_matches'] for x in module.review(download))
    assert all('/'+next(x['revision'] for x in data['plugins'] if x['repo'] in url)+'/LICENSE' in url for url in urls)
    assert not any(x['license_matches'] for x in module.review(lambda url:b'changed'))


def test_frozen_app_includes_catalog_and_licenses_and_install_option():
    spec=(ROOT/'native/mta_audio_editor_native.spec').read_text()
    assert 'optional_plugins_catalog.json' in spec and 'optional_plugin_licenses' in spec
    assert '--optional-plugins' in (ROOT/'native/mta_audio_editor_native.py').read_text()
    iss=(ROOT/'native/windows-installer.iss').read_text()
    assert iss.count('[Run]')==1 and 'Flags: unchecked' in iss
    result=subprocess.run(['bash','scripts/install_mta_native.sh','--dry-run','--vst3-plugins=mverb,dragonfly'],capture_output=True,text=True)
    assert result.returncode==0 and 'OPTIONAL_VST3=mverb,dragonfly' in result.stdout
