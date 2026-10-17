"""Admin-only persistent artifact byte policy and safe delivery ceilings."""
from pathlib import Path
import subprocess

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app import ai_arranger_runtime as queue, ai_payload_limits as limits


@pytest.fixture
def settings_api(tmp_path, monkeypatch):
    from app import main, auth
    monkeypatch.setattr(queue, '_ROOT', tmp_path / 'queue')
    monkeypatch.setattr(auth, 'session_user', lambda request:
        {'role': request.headers['x-test-role']} if request.headers.get('x-test-role') else None)
    api = FastAPI()
    api.add_api_route('/settings', main.admin_ai_execution_settings, methods=['GET'])
    api.add_api_route('/settings', main.admin_ai_execution_settings_update, methods=['PUT'])
    return TestClient(api)


def test_settings_authorization_and_persistence(settings_api):
    client = settings_api
    for method in ('get', 'put'):
        args = {'json': {'max_artifact_mib': 2048}} if method == 'put' else {}
        assert getattr(client, method)('/settings', **args).status_code == 401
        assert getattr(client, method)('/settings', headers={'x-test-role': 'user'}, **args).status_code == 403
    headers = {'x-test-role': 'admin'}
    assert client.get('/settings', headers=headers).json()['max_artifact_mib'] == 1024
    assert client.put('/settings', headers=headers, json={'max_artifact_mib': 4096}).status_code == 200
    assert queue.artifact_limit_mib() == 4096
    with queue._db() as con:
        assert con.execute("SELECT value FROM settings WHERE key='max_artifact_mib'").fetchone()[0] == '4096'
    assert client.put('/settings', headers=headers, json={'max_concurrent_jobs': 2}).status_code == 200
    assert client.get('/settings', headers=headers).json()['max_artifact_mib'] == 4096


@pytest.mark.parametrize('value', [True, False, '1024', 1024.5, None, 63, 8193, {}, []])
def test_invalid_size_cannot_partially_update_concurrency(settings_api, value):
    response = settings_api.put('/settings', headers={'x-test-role': 'admin'},
        json={'max_concurrent_jobs': 3, 'max_artifact_mib': value})
    assert response.status_code == 422
    assert queue._limit() == 1 and queue.artifact_limit_mib() == 1024


@pytest.mark.parametrize('value', ['garbage', '0', '8193', '01024', '1024.0'])
def test_invalid_worker_snapshot_fails_closed(monkeypatch, value):
    monkeypatch.setenv('MTA_AI_JOB_MAX_ARTIFACT_MIB', value)
    with pytest.raises(ValueError, match='trusted worker artifact'):
        limits.worker_artifact_bytes()


def test_worker_and_packager_use_trusted_size_without_changing_file_count(tmp_path, monkeypatch):
    from app import ai_worker_artifacts as artifacts
    from app.ai_unified_adapter import _artifacts
    monkeypatch.setattr(artifacts, 'MAX_ARTIFACT_BYTES', 4)
    path = tmp_path / 'notes.txt'; path.write_bytes(b'1234567')
    monkeypatch.delenv('MTA_AI_JOB_MAX_ARTIFACT_MIB', raising=False)
    with pytest.raises(RuntimeError, match='size limit'):
        _artifacts(tmp_path, [(path, 'text/plain')])
    monkeypatch.setenv('MTA_AI_JOB_MAX_ARTIFACT_MIB', '2048')
    assert limits.worker_artifact_bytes() == 2 * 1024**3
    _artifacts(tmp_path, [(path, 'text/plain')])
    assert artifacts.package_artifacts(tmp_path)[1] == 'application/zip'
    assert artifacts.MAX_FILES == 16
    with pytest.raises(ValueError, match='within limits'):
        artifacts.package_artifacts(tmp_path, max_bytes=4)


def test_response_reads_small_chunks_below_configured_ceiling():
    from app.ai_remote_client import _read_verified_result
    class Response:
        headers = {'Content-Type': 'application/json', 'X-MTA-AI-Job-ID': 'job'}
        def read(self, size):
            assert size <= 1024 * 1024
            return b'{}'
    assert _read_verified_result(Response())[0] == b'{}'


def test_admin_form_load_save_and_refresh_preserve_edits():
    source = Path('app/static/admin.js').read_text()
    section = source[source.index('let aiQueueRefreshTimer'):source.index('async function cancelAIQueueJob')]
    script = r'''
const vm=require('vm'),assert=require('assert');const nodes={};let saved;
const q=s=>nodes[s]||(nodes[s]={value:'',innerHTML:''});
const api=async(path,options)=>{if(path.includes('/settings')){if(options){saved=JSON.parse(options.body);return saved;}
return {max_concurrent_jobs:2,max_artifact_mib:2048,artifact_mib_min:64,artifact_mib_max:8192};}
return {jobs:[],max_concurrent_jobs:2};};
const ctx={q,api,alert:x=>{throw Error(x)},Number};vm.createContext(ctx);vm.runInContext(process.argv[1],ctx);
(async()=>{await ctx.loadAIQueue();assert.equal(q('#aiArtifactMaxMiB').value,2048);
q('#aiArtifactMaxMiB').value='4096';await ctx.loadAIQueue();assert.equal(q('#aiArtifactMaxMiB').value,'4096');
await ctx.saveAIQueueSettings();assert.deepEqual(saved,{max_concurrent_jobs:2,max_artifact_mib:4096});
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result = subprocess.run(['node', '-e', script, section], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    html = Path('app/templates/admin.html').read_text()
    assert 'id="aiArtifactMaxMiB"' in html and 'Dimensione massima artefatti' in html
