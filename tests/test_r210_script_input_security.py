"""Offline script boundaries reject unsafe protocols, redirects and XML entities."""
import importlib.util
import json
from pathlib import Path
from urllib.error import HTTPError

import pytest
from scripts import installed_diagnostics_r208 as diagnostics
from scripts import run_global_regression_shard as shard


def load(name,filename):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).resolve().parents[1]/filename)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('url',['file:///etc/hosts','ftp://example.test/repo','http://example.test/repo','https://user:secret@example.test/repo','https://example.test/repo#fragment'])
def test_public_repository_verifier_rejects_unsafe_url_before_network(monkeypatch,url):
    module=load('input_security_pages','scripts/repositories/verify_public_pages.py')
    def forbidden(*a,**kw):raise AssertionError('Network must not be opened')
    monkeypatch.setattr(module.http.client,'HTTPSConnection',forbidden)
    with pytest.raises(ValueError):module.fetch(url,'test-token',1)


def test_repository_verifier_does_not_follow_redirect_and_bounds_body(monkeypatch):
    module=load('input_security_pages','scripts/repositories/verify_public_pages.py');calls=[]
    class Response:
        status=302;reason='Redirect';headers={'Location':'file:///private'}
        def read(self,n):calls.append(('read',n));return b'payload'
    class Connection:
        def __init__(self,*a,**kw):calls.append(('connect',a))
        def request(self,*a,**kw):calls.append(('request',a))
        def getresponse(self):return Response()
        def close(self):calls.append(('close',))
    monkeypatch.setattr(module.http.client,'HTTPSConnection',Connection)
    with pytest.raises(HTTPError):module.fetch('https://example.test/repo?','token',1)
    assert not any(c[0]=='read' for c in calls)
    assert [c for c in calls if c[0]=='request']==[('request',('GET','/repo?mta_verify=token'))]
    Response.status=200;monkeypatch.setattr(module,'MAX_RESPONSE_BYTES',4)
    with pytest.raises(OSError,match='exceeds'):module.fetch('https://example.test/repo','token',1)
    assert ('read',5) in calls and calls[-1]==('close',)


@pytest.mark.parametrize('url',['file:///etc/hosts','ftp://example.test','https://user:secret@example.test'])
def test_installed_diagnostics_rejects_non_web_or_credentialed_urls(monkeypatch,url):
    monkeypatch.setattr(diagnostics.http.client,'HTTPSConnection',lambda *a,**kw:pytest.fail('Unexpected connection'))
    results=[];diagnostics.inspect_server(results,url)
    assert len(results)==1 and results[0]['name']=='server_url' and results[0]['status']=='FAIL'


def test_installed_diagnostics_never_follows_server_redirects(monkeypatch):
    calls=[]
    class Response:
        status=302;headers={'Content-Type':'text/html','Location':'file:///private'}
    class Connection:
        def __init__(self,host,port,**kw):calls.append(('host',host))
        def request(self,method,path,**kw):calls.append(('request',path))
        def getresponse(self):return Response()
        def close(self):pass
    monkeypatch.setattr(diagnostics.http.client,'HTTPSConnection',Connection)
    monkeypatch.setattr(diagnostics.shutil,'which',lambda *a:None)
    results=[];diagnostics.inspect_server(results,'https://example.test/mta')
    assert len([c for c in calls if c==('host','example.test')])==3
    assert all(path.startswith('/mta/') for action,path in calls if action=='request')
    assert not any('private' in str(c) for c in calls)


def test_repository_xml_entity_expansion_is_rejected(tmp_path):
    from test_r209_pages_rpm_distribution import _staging
    module=load('input_security_xml','scripts/repositories/publish_pages_rpm_indexes.py')
    staging=_staging(tmp_path)
    (staging/'rpm/early/el9/repodata/repomd.xml').write_text('<!DOCTYPE x [<!ENTITY leaked "forbidden expansion">]><repomd>&leaked;</repomd>')
    with pytest.raises(ValueError,match='forbidden'):module.populate(staging,tmp_path/'pages','early','https://github.com/example/repo/releases/download/test/')


def test_malicious_junit_produces_failed_shard_report_not_success(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path);(tmp_path/'tests').mkdir();(tmp_path/'tests/test_example.py').write_text('')
    class Process:
        def __init__(self,command,**kw):
            output=next(arg.split('=',1)[1] for arg in command if arg.startswith('--junitxml='))
            Path(output).write_text('<!DOCTYPE x [<!ENTITY count "5">]><testsuite tests="&count;"/>')
        def wait(self,**kw):return 0
    monkeypatch.setattr(shard.subprocess,'Popen',Process)
    assert shard.main(['--shards','1','--shard','0','--output-dir',str(tmp_path/'reports')])==2
    report=json.loads((tmp_path/'reports/shard-00-of-01.json').read_text())
    assert report['counts'] is None and report['exit_code']!=0
