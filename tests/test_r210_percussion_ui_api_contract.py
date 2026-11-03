"""Production UI consumes real router/core responses; neural inference is forbidden."""
import hashlib
import io
import json
from pathlib import Path
import subprocess

import numpy as np
import pytest
import soundfile as sf
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import account_lifecycle, auth, percussion_adapters as adapters
from app import percussion_benchmark as bench, percussion_benchmark_routes as routes
from app import percussion_corpus as corpus
from test_r210_percussion_benchmark_ui import HARNESS


ROOT = Path(__file__).resolve().parents[1]
BASE = '/api/admin/ai-benchmarks'
ACTUAL_ADAPTER_CATALOG = adapters.catalog


@pytest.fixture
def benchmark_api(tmp_path, monkeypatch):
    """An isolated admin route fixture, not authentication or checkpoint evidence."""
    monkeypatch.setattr(auth, 'DATA_ROOT', tmp_path / 'data')
    monkeypatch.setattr(auth, 'require_admin', lambda request: {'id': 7, 'role': 'admin'})
    monkeypatch.setattr(account_lifecycle, 'is_deleted', lambda actor: False)
    model = {'id': 'mvsep-mega53', 'name': 'Unavailable contract fixture', 'version': 'fixture-v1',
             'enabled': True, 'checkpoint_sha256': None, 'license': 'Synthetic metadata only',
             'status': {'state': 'not_installed', 'ready': False, 'reason': 'No checkpoint is installed in this fixture'}}
    monkeypatch.setattr(adapters, 'catalog', lambda: {'models': [model]})

    def forbidden(*args, **kwargs):
        pytest.fail('UI/API contract fixtures must not dispatch model inference')
    monkeypatch.setattr(adapters, 'infer', forbidden)
    dataset = bench.root() / 'datasets' / 'ui-contract-v1'
    dataset.mkdir(parents=True)
    samples = np.sin(np.arange(8000) * .07)[:, None] * .15
    files = {}
    for name, audio in [('drums.wav', samples), ('mix.wav', samples * .9), ('reference.wav', samples * .5)]:
        sf.write(dataset / name, audio, 16000, subtype='PCM_24')
        files[name] = hashlib.sha256((dataset / name).read_bytes()).hexdigest()
    manifest = {'schema': corpus.CORPUS_VERSION, 'id': 'ui-contract-v1', 'name': 'Original diagnostic fixture',
                'counts': {'declared': 1, 'prepared': 1, 'synthetic': 1, 'negative': 0, 'real': 0, 'real_unavailable': 0},
                'cases': [{'id': 'shaker-hihat', 'title': 'Diagnostic waveform, not a recording', 'group': 'synthetic',
                           'category': 'shaker_hihat', 'prepared': True, 'exact_ground_truth': True,
                           'family_id': 'ui-original-fixture', 'split': 'test', 'duration_seconds': .5,
                           'frames': 8000, 'sample_rate': 16000, 'channels': 1,
                           'input_drums': 'drums.wav', 'input_mix': 'mix.wav',
                           'references': {'include_kick': 'reference.wav', 'exclude_kick': 'reference.wav'},
                           'mix_references': {'include_kick': 'reference.wav', 'exclude_kick': 'reference.wav'},
                           'sources': {}, 'sha256': files}]}
    (dataset / 'manifest.json').write_text(json.dumps(manifest))
    assert corpus.load(dataset)['id'] == 'ui-contract-v1'
    app = FastAPI(); app.include_router(routes.router)
    return TestClient(app, headers={'X-MTA-Request': '1'})


def campaign(client):
    response = client.post(BASE + '/campaigns', json={
        'title': 'Actual API contract', 'kind': 'experimental', 'model_ids': ['mvsep-mega53'],
        'dataset_ids': ['ui-contract-v1'], 'seed': 42,
        'options': {'include_kick': True, 'clap': 'excluded', 'timpani': 'excluded', 'source_mode': 'both'}})
    assert response.status_code == 200, response.text
    return response.json()['campaign']['id']


def production_ui(responses, checks):
    api = r'''
const actualResponses=RESPONSES;
async function fetch(url,options){
 calls.push({url,options});
 const key=options.method+' '+url;
 if(!(key in actualResponses))throw Error('Uncollected API response: '+key);
 const entry=actualResponses[key];return {ok:entry.status>=200&&entry.status<300,status:entry.status,json:async()=>entry.body};
}
'''.replace('RESPONSES', json.dumps(responses))
    result = subprocess.run(['node'], input=HARNESS + (ROOT / 'app/static/percussion_benchmark.js').read_text() + api + checks,
                            text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout) if result.stdout.strip() else None


def actual_response(response):
    return {'status': response.status_code, 'body': response.json()}


def test_real_catalog_and_create_response_accept_the_production_ui_payload(benchmark_api):
    client = benchmark_api; cid = campaign(client)
    responses = {
        'GET ' + BASE + '/catalog': actual_response(client.get(BASE + '/catalog')),
        'GET ' + BASE + '/campaigns': actual_response(client.get(BASE + '/campaigns')),
        'GET ' + BASE + '/campaigns/' + cid: actual_response(client.get(BASE + '/campaigns/' + cid)),
        'POST ' + BASE + '/campaigns': actual_response(client.get(BASE + '/campaigns/' + cid)),
    }
    payload = production_ui(responses, r'''
(async()=>{
 const host=new Node('div'),view=await window.MtaBenchmark.open(host);
 const setup=byClass(host,'benchmark-setup');
 const check=walk(setup).find(n=>n.tagName==='INPUT'&&n.value==='mvsep-mega53');
 assert.ok(check);assert.equal(check.disabled,false);check.checked=true;
 const dataset=walk(setup).find(n=>n.tagName==='INPUT'&&n.value==='ui-contract-v1');assert.equal(dataset.checked,true);
 await buttons(setup).find(n=>n.textContent==='Crea campagna').click();
 const request=calls.find(c=>c.url.endsWith('/campaigns')&&c.options.method==='POST');
 assert.ok(request,byClass(host,'benchmark-status').textContent);
 console.log(request.options.body);view.dispose();
})().catch(e=>{console.error(e);process.exitCode=1});
''')
    assert payload['options']['source_mode'] == 'both'
    assert payload['options']['include_kick'] is True
    response = client.post(BASE + '/campaigns', json=payload)
    assert response.status_code == 200, response.text
    created = response.json()
    assert created['campaign']['counts']['total'] == 2
    assert len(created['cases']) == 2
    assert created['approval']['can_approve'] is False
    assert 'manual_approval' not in created['campaign']


def test_unavailable_actual_results_render_without_inventing_hidden_summary_or_approval(benchmark_api):
    client = benchmark_api; cid = campaign(client)
    # The real runner records unavailable entries; inference is forbidden by the
    # fixture. No audio quality or model execution is represented as successful.
    bench.run(cid, 7)
    response = client.get(BASE + '/campaigns/' + cid)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['campaign']['counts']['completed'] == 0
    assert body['campaign']['counts']['unavailable'] == 2
    assert all(row['status'] == 'not_installed' for row in body['results'])
    has_categories = bool(body['summary'].get('categories'))
    if has_categories:
        assert isinstance(body['summary']['categories'], (dict, list))
    responses = {
        'GET ' + BASE + '/catalog': actual_response(client.get(BASE + '/catalog')),
        'GET ' + BASE + '/campaigns': actual_response(client.get(BASE + '/campaigns')),
        'GET ' + BASE + '/campaigns/' + cid: actual_response(response),
    }
    production_ui(responses, r'''
(async()=>{
 const host=new Node('div'),view=await window.MtaBenchmark.open(host);
 await view.openCampaign(CAMPAIGN);
 const current=byClass(host,'benchmark-current');
 assert.ok(current.textContent.includes('Non installato'));assert.ok(current.textContent.includes('2/2'));
 assert.equal(current.textContent.includes('Per categoria'),HAS_CATEGORIES);assert.ok(current.textContent.includes('shaker_hihat'));
 assert.equal(buttons(byClass(host,'benchmark-final-approval')).length,0);
 assert.equal(calls.some(c=>c.url.endsWith('/approve')),false);
 view.dispose();
})().catch(e=>{console.error(e);process.exitCode=1});
'''.replace('CAMPAIGN', json.dumps(cid)).replace('HAS_CATEGORIES', json.dumps(has_categories)))


def test_actual_blind_and_source_audio_routes_offer_no_unexecuted_candidate(benchmark_api):
    client = benchmark_api; cid = campaign(client)
    details = client.get(BASE + '/campaigns/' + cid)
    case_id = details.json()['cases'][0]['id']
    blind_url = BASE + f'/campaigns/{cid}/blind?case_id={case_id}'
    blind = client.get(blind_url)
    assert blind.status_code == 200, blind.text
    assert blind.json()['candidates'] == []
    for role in ('input_url', 'reference_url'):
        url = blind.json()[role]
        assert url.startswith(BASE + f'/campaigns/{cid}/cases/')
        response = client.get(url)
        assert response.status_code == 200, response.text
        assert response.headers['content-type'].startswith('audio/wav')
        assert 'no-store' in response.headers['cache-control']
        with sf.SoundFile(io.BytesIO(response.content)) as wave:
            assert wave.frames == 8000 and wave.samplerate == 16000
    responses = {
        'GET ' + BASE + '/catalog': actual_response(client.get(BASE + '/catalog')),
        'GET ' + BASE + '/campaigns': actual_response(client.get(BASE + '/campaigns')),
        'GET ' + BASE + '/campaigns/' + cid: actual_response(details),
        'GET ' + blind_url: actual_response(blind),
    }
    production_ui(responses, r'''
(async()=>{
 const host=new Node('div'),view=await window.MtaBenchmark.open(host);
 await view.openCampaign(CAMPAIGN);await view.openCase(CASE);
 const panel=byClass(host,'benchmark-listening');
 assert.ok(panel.textContent.includes('Nessun output tecnicamente valido'));
 assert.equal(walk(panel).filter(n=>n.tagName==='FORM').length,0);
 const play=buttons(byClass(panel,'benchmark-ab-choices')).find(n=>n.textContent==='DRUMS originale');
 assert.ok(play);await play.click();
 const audio=find(panel,n=>n.tagName==='AUDIO');assert.ok(audio.src.includes('/cases/'));assert.equal(audio.paused,false);
 assert.equal(calls.some(c=>c.url.endsWith('/ratings')),false);assert.equal(calls.some(c=>c.url.endsWith('/approve')),false);
 view.dispose();
})().catch(e=>{console.error(e);process.exitCode=1});
'''.replace('CAMPAIGN', json.dumps(cid)).replace('CASE', json.dumps(case_id)))


def test_real_adapter_catalog_keeps_core_activation_version_and_weight_license_fields(benchmark_api, monkeypatch):
    monkeypatch.setattr(adapters, 'catalog', ACTUAL_ADAPTER_CATALOG)
    response = benchmark_api.get(BASE + '/catalog')
    assert response.status_code == 200, response.text
    metadata = {item['id']: item for item in json.loads(adapters.CATALOG_PATH.read_text())['models']}
    enabled = set(adapters.enabled_models())
    actual = response.json()['models']
    assert set(metadata) == {item['id'] for item in actual}
    for model in actual:
        original = metadata[model['id']]
        assert type(model.get('enabled')) is bool, f"Missing activation state for {model['id']}"
        assert model['enabled'] is (model['id'] in enabled)
        assert model.get('version') == original.get('checkpoint_revision'), f"Incorrect model version for {model['id']}"
        licence = model.get('license')
        displayed_licence = licence.get('status') if isinstance(licence, dict) else licence
        assert displayed_licence == original.get('weights_license'), f"Incorrect weight licence for {model['id']}"
        assert isinstance(model['status'], str)


def test_professional_listening_consent_generated_by_ui_is_bound_by_actual_rating_api(benchmark_api, monkeypatch):
    """A synthetic adapter fixture exercises ratings, never neural quality evidence."""
    model = next(item for item in adapters._metadata()['models'] if item['id'] == 'mvsep-mega53')
    monkeypatch.setattr(adapters, 'catalog', lambda: {'models': [{**model, 'enabled': True,
                        'status': {'state': 'ready', 'ready': True, 'reason': 'Synthetic API contract fixture'}}]})
    monkeypatch.setattr(adapters, 'enabled_models', lambda: ['mvsep-mega53'])
    monkeypatch.setattr(adapters, 'verify_installation', lambda request: None)
    fixture_calls = []

    def synthetic_adapter(request, source, output_dir, **kwargs):
        fixture_calls.append(source)
        values, rate = sf.read(source, always_2d=True)
        output = output_dir / 'fixture-output.wav'
        sf.write(output, values * .5, rate, subtype='PCM_24')
        return {'output': output, 'model_version': request.model_version,
                'checkpoint_sha256': request.checkpoint_sha256, 'profile_sha256': request.profile_sha256,
                'inference_completed': True, 'execution_profile': {'fixture': 'procedural waveform only'}}

    monkeypatch.setattr(adapters, 'infer', synthetic_adapter)
    client = benchmark_api; cid = campaign(client)
    result = bench.run(cid, 7)
    assert len(fixture_calls) == 2
    assert all(row['status'] == 'validated_automatically' for row in result['results']), result['results']
    details = client.get(BASE + '/campaigns/' + cid)
    case_id = details.json()['cases'][0]['id']
    blind_url = BASE + f'/campaigns/{cid}/blind?case_id={case_id}'
    blind = client.get(blind_url)
    assert blind.status_code == 200, blind.text
    assert len(blind.json()['candidates']) == 1
    rating_url = BASE + f'/campaigns/{cid}/ratings'
    responses = {
        'GET ' + BASE + '/catalog': actual_response(client.get(BASE + '/catalog')),
        'GET ' + BASE + '/campaigns': actual_response(client.get(BASE + '/campaigns')),
        'GET ' + BASE + '/campaigns/' + cid: actual_response(details),
        'GET ' + blind_url: actual_response(blind),
        # The form's write is captured, then submitted to the actual API below.
        'POST ' + rating_url: {'status': 200, 'body': {}},
    }
    payload = production_ui(responses, r'''
(async()=>{
 const host=new Node('div'),view=await window.MtaBenchmark.open(host);
 await view.openCampaign(CAMPAIGN);await view.openCase(CASE);
 const form=find(byClass(host,'benchmark-listening'),n=>n.tagName==='FORM'),fields=walk(form).filter(n=>n.tagName==='SELECT');
 for(let i=0;i<6;i++)fields[i].value='4';fields[6].value='professional';await fields[6].emit('change');
 const row=walk(form).find(n=>n.classes.has('benchmark-professional-consent')),consent=find(row,n=>n.tagName==='INPUT');
 assert.equal(consent.checked,false);await form.emit('submit');assert.equal(calls.some(c=>c.url.endsWith('/ratings')),false);
 consent.checked=true;await form.emit('submit');
 console.log(calls.find(c=>c.url.endsWith('/ratings')).options.body);
 assert.equal(calls.some(c=>c.url.endsWith('/approve')),false);view.dispose();
})().catch(e=>{console.error(e);process.exitCode=1});
'''.replace('CAMPAIGN', json.dumps(cid)).replace('CASE', json.dumps(case_id)))
    assert payload['explicit_approval'] is True and payload['decision'] == 'professional'
    response = client.post(rating_url, json=payload)
    assert response.status_code == 200, response.text
    rating = response.json()['rating']
    assert rating['explicit_approval'] is True
    assert rating['binding']['config_sha256'] == details.json()['campaign']['config_sha256']
    refreshed = client.get(BASE + '/campaigns/' + cid).json()
    assert 'manual_approval' not in refreshed['campaign']
    assert refreshed['approval']['approved'] is False
    assert refreshed['approval']['can_approve'] is False
