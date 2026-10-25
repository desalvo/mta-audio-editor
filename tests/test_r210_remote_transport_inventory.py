"""Review inventory rejects new aliases, changed source and missing dispositions."""
import copy
import importlib.util
import json
import hashlib
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('remote_inventory',ROOT/'scripts/check_remote_transport_inventory.py')
inventory=importlib.util.module_from_spec(spec);spec.loader.exec_module(inventory)


def fixture(tmp_path,source='from urllib.request import urlopen as fetch\ndef run():\n    return fetch("https://example.test")\n'):
    app=tmp_path/'app';app.mkdir();(app/'worker.py').write_text(source)
    sites=inventory.discover(tmp_path)
    return {'schema':'mta-remote-transport-review-1','checker_sha256':hashlib.sha256(Path(inventory.__file__).read_bytes()).hexdigest(),'sites':[{**site,'category':'inference_guarded',
        'boundary':'A reviewed test-only explicit network boundary with no execution.',
        'verification':'Verified fixture inventory mutation tests; no real network.'} for site in sites]}


def test_current_inventory_matches_review():
    review=json.loads((ROOT/'docs/security/REMOTE_TRANSPORT_REVIEW_R210.json').read_text())
    result=inventory.validate(ROOT,review)
    assert result['inventory_passed'] and result['remote_model_attestation_complete'] is False
    assert result['reviewed_sites']>=27


@pytest.mark.parametrize('source',[
    'from urllib.request import urlopen as hidden\nhidden("https://example.test")',
    'import httpx as hidden\nhidden.Client()',
    'from httpx import AsyncClient as hidden\nhidden()',
    'from urllib.request import build_opener as hidden\nx=hidden()\nx.open("https://example.test")',
    'import socket as hidden\nhidden.create_connection(("example.test",443))',
    'import aiohttp as hidden\nhidden.ClientSession()',
])
def test_new_aliased_transports_require_review(tmp_path,source):
    review=fixture(tmp_path);(tmp_path/'app/new.py').write_text(source)
    assert len(inventory.discover(tmp_path))>1
    with pytest.raises(ValueError,match='boundary'):inventory.validate(tmp_path,review)


@pytest.mark.parametrize('change',['source','missing','category','rationale','hash','checker','reorder'])
def test_inventory_cannot_silently_approve_drift(tmp_path,change):
    review=fixture(tmp_path)
    if change=='source':
        p=tmp_path/'app/worker.py';p.write_text(p.read_text()+'\n# changed transport admission\n')
    elif change=='missing':review['sites']=[]
    elif change=='category':review['sites'][0]['category']='approved'
    elif change=='rationale':review['sites'][0]['boundary']='ok'
    elif change=='hash':review['sites'][0]['source_sha256']='0'*64
    elif change=='checker':review['checker_sha256']='0'*64
    else:review['sites'].append(copy.deepcopy(review['sites'][0]))
    with pytest.raises(ValueError):inventory.validate(tmp_path,review)


@pytest.mark.parametrize('path',['/api/ai-gateway/v1/generate','/api/ai-jobs/execute-audio/whisper','/api/ai-device/start?x=1'])
def test_native_authorization_helper_cannot_be_repurposed_for_inference(monkeypatch,path):
    from app import native_ai_account
    def forbidden(*args,**kwargs):raise AssertionError('No transport')
    monkeypatch.setattr(native_ai_account,'build_opener',forbidden)
    with pytest.raises(ValueError,match='authorization path'):native_ai_account._request('https://example.test',path,{})


@pytest.mark.parametrize('path',['/api/ai-device/start','/api/ai-device/poll'])
def test_supported_device_authorization_still_uses_exact_post(monkeypatch,path):
    from app import native_ai_account
    sent=[]
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,*args):return b'{"state":"pending"}'
    class Opener:
        def open(self,request,**kwargs):sent.append(request);return Response()
    monkeypatch.setattr(native_ai_account,'build_opener',lambda *args:Opener())
    assert native_ai_account._request('https://example.test',path,{'client_id':'fixture'})=={'state':'pending'}
    assert len(sent)==1 and sent[0].full_url=='https://example.test'+path and sent[0].method=='POST'
