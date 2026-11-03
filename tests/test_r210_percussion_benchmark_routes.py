"""Real admin sessions protect benchmark effects, uploads and queue cancellation."""
import json

import pytest
from fastapi.testclient import TestClient

from app import auth, percussion_adapters as adapters, percussion_benchmark as bench
from app import percussion_benchmark_routes as routes, ai_arranger_runtime as queue
from test_r210_legal_documents import cookie
from test_r210_percussion_dataset_import import dataset as dataset, archive  # noqa: F401


BASE = '/api/admin/ai-benchmarks'
AUTH_CASES = [
    ('GET', '/catalog', None), ('POST', '/datasets/synthetic', {}),
    ('POST', '/datasets/import', 'multipart'), ('POST', '/models/mvsep-mega53/verify', {}),
    ('PUT', '/models/mvsep-mega53/enabled', {'enabled': False}), ('GET', '/campaigns', None),
    ('POST', '/campaigns', {'title': 'Blocked'}), ('POST', '/campaigns/restore', 'multipart'),
    ('GET', '/campaigns/example', None), ('POST', '/campaigns/example/run', {}),
    ('POST', '/campaigns/example/cancel', {}), ('GET', '/campaigns/example/blind?case_id=case', None),
    ('GET', '/campaigns/example/audio/candidate', None), ('GET', '/campaigns/example/cases/case/input', None),
    ('POST', '/campaigns/example/ratings', {}), ('POST', '/campaigns/example/approve', {}),
    ('GET', '/campaigns/example/export', None), ('GET', '/campaigns/example/reports', None),
]


@pytest.fixture
def admin_api(tmp_path, monkeypatch):
    from app import main
    monkeypatch.setattr(auth, 'DATA_ROOT', tmp_path / 'auth')
    monkeypatch.setattr(queue, '_ROOT', tmp_path / 'queue')
    monkeypatch.setenv('MTA_ADMIN_PASSWORD', 'percussion-admin-route-test-password')
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH', raising=False)
    monkeypatch.delenv('MTA_NATIVE_SINGLE_USER', raising=False)
    monkeypatch.setattr(main, 'NATIVE_SINGLE_USER', False)
    monkeypatch.setattr(main, 'check_basic_auth', lambda request: False)
    auth.init_auth_db()
    admin = auth.find_user('admin')['id']
    with auth.db() as con:
        con.execute("INSERT INTO users(username,email,password_hash,active,email_confirmed,role,created_at,updated_at) VALUES('bench-reader','bench-reader@example.test','unused',1,1,'user',1,1)")
    reader = auth.find_user('bench-reader')['id']
    client = TestClient(main.app, headers={'X-MTA-Request': '1'})
    return client, admin, reader


def login(client, uid):
    client.cookies.update(cookie(uid))


@pytest.mark.parametrize('method,path,body', AUTH_CASES)
@pytest.mark.parametrize('identity', ['anonymous', 'reader'])
def test_all_benchmark_routes_require_registered_administrator_before_effects(admin_api, monkeypatch, identity, method, path, body):
    client, admin, reader = admin_api
    if identity == 'reader':
        login(client, reader)
    called = []
    for name in ('catalog', 'prepare_synthetic', 'create', 'campaigns', 'get', 'start', 'restore', 'blind', 'audio', 'case_audio', 'rate', 'approve', 'export', 'reports'):
        monkeypatch.setattr(bench, name, lambda *a, **k: called.append('forbidden'))
    monkeypatch.setattr(adapters, 'verify', lambda *a, **k: called.append('forbidden'))
    kwargs = {}
    if body == 'multipart':
        kwargs['files'] = {'file': ('data.zip', b'not-a-zip', 'application/zip')}
        kwargs['data'] = {'acknowledge_rights': 'true'}
    elif body is not None:
        kwargs['json'] = body
    response = client.request(method, BASE + path, **kwargs)
    assert response.status_code == (401 if identity == 'anonymous' else 403), response.text
    assert not called and not (auth.DATA_ROOT / 'ai-benchmarks').exists()


def test_actual_main_csrf_guard_rejects_admin_write_without_request_header(admin_api, monkeypatch):
    client, admin, reader = admin_api;login(client, admin)
    client.headers.pop('X-MTA-Request')
    called = [];monkeypatch.setattr(bench, 'prepare_synthetic', lambda: called.append('forbidden'))
    assert client.post(BASE + '/datasets/synthetic', json={}).status_code == 403
    assert not called


def test_admin_actor_is_server_derived_for_create_run_ratings_and_final_approval(admin_api, monkeypatch):
    client, admin, reader = admin_api;login(client, admin)
    calls = []
    monkeypatch.setattr(bench, 'create', lambda body, actor: calls.append(('create', body, actor)) or {'campaign': {'id': 'c'}})
    monkeypatch.setattr(bench, 'start', lambda cid, actor, retry_failed=False: calls.append(('run', cid, actor, retry_failed)) or {'campaign': {'id': cid}})
    monkeypatch.setattr(bench, 'rate', lambda cid, body, actor: calls.append(('rating', cid, body, actor)) or {'rating': {'actor_user_id': actor}})
    monkeypatch.setattr(bench, 'approve', lambda cid, body, actor: calls.append(('approval', cid, body, actor)) or {'approval': {'approved': False}})
    create = {'title': 'Campaign', 'kind': 'experimental', 'model_ids': ['mvsep-mega53'], 'dataset_ids': ['d']}
    assert client.post(BASE + '/campaigns', json=create).status_code == 200
    assert client.post(BASE + '/campaigns/c/run', json={'retry_failed': True}).status_code == 200
    rating = {'case_id': 'd--case--drums', 'candidate_id': 'opaque', 'scores': {}, 'decision': 'limited', 'explicit_approval': False}
    assert client.post(BASE + '/campaigns/c/ratings', json=rating).status_code == 200
    assert client.post(BASE + '/campaigns/c/approve', json={'confirm': True, 'configuration_sha256': 'a' * 64}).status_code == 200
    assert calls == [('create', create, admin), ('run', 'c', admin, True), ('rating', 'c', rating, admin),
                     ('approval', 'c', {'confirm': True, 'configuration_sha256': 'a' * 64}, admin)]


@pytest.mark.parametrize('body', [{'retry_failed': 'true'}, {'retry_failed': 1}, {'retry_failed': False, 'actor_user_id': 123}])
def test_run_rejects_actor_or_retry_overrides(admin_api, monkeypatch, body):
    client, admin, reader = admin_api;login(client, admin)
    calls = [];monkeypatch.setattr(bench, 'start', lambda *a, **k: calls.append('forbidden'))
    assert client.post(BASE + '/campaigns/c/run', json=body).status_code == 400
    assert not calls


def test_long_composite_case_keys_reach_blind_and_source_audio_without_truncation(admin_api, monkeypatch):
    client, admin, reader = admin_api;login(client, admin)
    key = 'd' * 80 + '--' + 'c' * 80 + '--drums'
    calls = []
    monkeypatch.setattr(bench, 'blind', lambda cid, case: calls.append((cid, case)) or {'case': {'id': case}, 'candidates': []})
    monkeypatch.setattr(bench, 'case_audio', lambda cid, case, role: calls.append((cid, case, role)) or b'WAVE fixture')
    response = client.get(BASE + '/campaigns/c/blind', params={'case_id': key})
    assert response.status_code == 200 and response.json()['case']['id'] == key
    response = client.get(BASE + '/campaigns/c/cases/' + key + '/input')
    assert response.status_code == 200 and response.content == b'WAVE fixture'
    assert calls == [('c', key), ('c', key, 'input')]
    assert 'no-store' in response.headers['cache-control']
    assert response.headers['x-content-type-options'] == 'nosniff'


@pytest.mark.parametrize('key', ['../escape', '/absolute', 'case?bad', 'x' * 257])
def test_unsafe_case_lookup_keys_never_reach_core(admin_api, monkeypatch, key):
    client, admin, reader = admin_api;login(client, admin)
    calls = [];monkeypatch.setattr(bench, 'blind', lambda *a: calls.append('forbidden'))
    assert client.get(BASE + '/campaigns/c/blind', params={'case_id': key}).status_code == 400
    assert not calls


def test_audio_matching_and_zip_reports_contracts_are_private_admin_downloads(admin_api, monkeypatch):
    client, admin, reader = admin_api;login(client, admin)
    calls = [];monkeypatch.setattr(bench, 'audio', lambda cid, candidate, matched: calls.append((cid, candidate, matched)) or b'actual-test-bytes')
    response = client.get(BASE + '/campaigns/c/audio/opaque?matched=true')
    assert response.status_code == 200 and response.content == b'actual-test-bytes'
    assert calls == [('c', 'opaque', True)] and response.headers['content-type'] == 'audio/wav'
    monkeypatch.setattr(bench, 'export', lambda cid: b'archive fixture')
    response = client.get(BASE + '/campaigns/c/export')
    assert response.content == b'archive fixture' and response.headers['content-type'] == 'application/zip'
    assert 'mta-percussion-c.zip' in response.headers['content-disposition']
    monkeypatch.setattr(bench, 'reports', lambda cid: {'campaign': cid, 'warning': 'Human approval is not automatic'})
    assert client.get(BASE + '/campaigns/c/reports').json()['campaign'] == 'c'


@pytest.mark.parametrize('acknowledge', [None, 'false', 'TRUE', '1'])
def test_recording_import_requires_literal_explicit_rights_acknowledgement(admin_api, monkeypatch, acknowledge):
    client, admin, reader = admin_api;login(client, admin)
    calls = [];monkeypatch.setattr(routes.dataset_import, 'archive_identifier', lambda data: calls.append('forbidden'))
    data = {} if acknowledge is None else {'acknowledge_rights': acknowledge}
    assert client.post(BASE + '/datasets/import', data=data, files={'file': ('data.zip', b'zip', 'application/zip')}).status_code == 400
    assert not calls


def test_genuine_recording_import_uses_manifest_destination_and_authenticated_actor(admin_api, dataset):
    client, admin, reader = admin_api;login(client, admin)
    manifest, files = dataset
    response = client.post(BASE + '/datasets/import', data={'acknowledge_rights': 'true'},
                           files={'file': ('data.zip', archive(manifest, files), 'application/zip')})
    assert response.status_code == 200, response.text
    value = response.json()['dataset']
    assert value['id'] == manifest['id']
    saved = json.loads((bench.root() / 'datasets' / manifest['id'] / 'manifest.json').read_text())
    assert saved['import_record']['actor_user_id'] == admin
    assert not saved['import_record']['professional_quality_approval']
    assert client.post(BASE + '/datasets/import', data={'acknowledge_rights': 'true'},
                       files={'file': ('same.zip', archive(manifest, files), 'application/zip')}).status_code == 400


def test_restore_upload_is_bounded_and_original_actor_comes_from_session(admin_api, monkeypatch):
    client, admin, reader = admin_api;login(client, admin)
    calls = [];monkeypatch.setattr(bench, 'restore', lambda data, actor: calls.append((data, actor)) or {'campaign': {'id': 'restored'}})
    assert client.post(BASE + '/campaigns/restore', files={'file': ('saved.zip', b'zip fixture', 'application/zip')}).status_code == 200
    assert calls == [(b'zip fixture', admin)]
    monkeypatch.setattr(bench, 'MAX_ARCHIVE_BYTES', 4)
    assert client.post(BASE + '/campaigns/restore', files={'file': ('large.zip', b'12345', 'application/zip')}).status_code == 413
    assert len(calls) == 1
    assert client.post(BASE + '/campaigns/restore', files={'file': ('empty.zip', b'', 'application/zip')}).status_code == 400


@pytest.fixture
def saved_campaign(admin_api, dataset):
    client, admin, reader = admin_api;login(client, admin)
    manifest, files = dataset
    response = client.post(BASE + '/datasets/import', data={'acknowledge_rights': 'true'},
                           files={'file': ('recordings.zip', archive(manifest, files), 'application/zip')})
    assert response.status_code == 200, response.text
    response = client.post(BASE + '/campaigns', json={'title': 'Queue cancellation fixture', 'kind': 'release',
        'model_ids': ['mvsep-mega53'], 'dataset_ids': [manifest['id']], 'seed': 42,
        'options': {'include_kick': True, 'clap': 'excluded', 'timpani': 'excluded', 'source_mode': 'drums'}})
    assert response.status_code == 200, response.text
    return client, admin, response.json()['campaign']['id']


def test_cancel_reaches_original_real_durable_queue_job_and_publishes_cancelled_campaign(saved_campaign):
    client, admin, cid = saved_campaign
    accepted, job = queue.start('benchmark-' + cid, 'percussion-benchmark', lambda *a: None,
                                defer_spawn=True, cancellable=True, payload={'actor_user_id': admin, 'campaign_id': cid})
    assert accepted and job['state'] == 'queued'
    with bench.locked(cid):
        value = bench._read(cid);value['queue_job_id'] = job['job_id'];value['status'] = 'queued'
        bench._write(bench.folder(cid) / 'campaign.json', value)
    response = client.post(BASE + '/campaigns/' + cid + '/cancel', json={})
    assert response.status_code == 200, response.text
    assert response.json()['job']['state'] == 'cancelled'
    assert response.json()['campaign']['status'] == 'cancelled'
    assert queue.get(job['job_id'])['state'] == 'cancelled'
    assert not response.json()['approval']['can_approve']


def test_cancel_refuses_forged_unrelated_queue_job_and_does_not_change_it(saved_campaign):
    client, admin, cid = saved_campaign
    accepted, job = queue.start('another-project', 'arranger', lambda *a: None,
                                defer_spawn=True, payload={'actor_user_id': admin})
    assert accepted
    with bench.locked(cid):
        value = bench._read(cid);value['queue_job_id'] = job['job_id']
        bench._write(bench.folder(cid) / 'campaign.json', value)
    assert client.post(BASE + '/campaigns/' + cid + '/cancel', json={}).status_code == 400
    assert queue.get(job['job_id'])['state'] == 'queued'


def test_unrun_campaign_cannot_receive_professional_approval_and_reports_keep_human_pending(saved_campaign):
    client, admin, cid = saved_campaign
    state = client.get(BASE + '/campaigns/' + cid).json()
    assert not state['approval']['can_approve']
    response = client.post(BASE + '/campaigns/' + cid + '/approve', json={'confirm': True,
        'configuration_sha256': state['approval']['configuration_sha256'], 'comment': 'Cannot approve missing inference'})
    assert response.status_code == 400
    report = client.get(BASE + '/campaigns/' + cid + '/reports')
    assert report.status_code == 200 and not report.json()['summary']['professional_approval']
    assert not bench._read(cid).get('manual_approval')
