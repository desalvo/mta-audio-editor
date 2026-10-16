"""Installed-file worker startup, actual tab handlers and protected ZIP API."""
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import zipfile
import io

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_installed_worker_starts_outside_package(tmp_path):
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    for args in ([str(ROOT / 'app/ace_step_http_worker.py')], ['-m', 'app.ace_step_http_worker']):
        result = subprocess.run([sys.executable, *args, '--capabilities'],
                                cwd=tmp_path if len(args) == 1 else ROOT,
                                env=env, capture_output=True, text=True, timeout=15)
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)['supports_audio_input'] is True


def test_diagnostics_tab_handler_shows_panel_and_loads_settings():
    # Execute the shipped JS, including a failed API request, in a minimal DOM.
    script = r'''
const fs=require('fs'), vm=require('vm'), assert=require('assert');
const tabs=['web','storage','users','smtp','models','aiQueue','diagnostics'];
const buttons=tabs.map(tab=>({dataset:{tab},classList:{toggle(){}}}));
const elements=Object.fromEntries(tabs.map(tab=>['#'+tab+'Tab',{hidden:tab!=='web'}]));
for(const id of ['diagnosticsEnabled','diagnosticsStatus','smtpForm','webSettingsSummary'])elements['#'+id]={};
let fail=false;
const context={console,document:{querySelector:s=>elements[s],querySelectorAll:()=>buttons},
fetch:async url=>({ok:!fail,headers:{get:()=> 'application/json'},json:async()=>url.includes('diagnostics')?{enabled:true}:{disk:{},models:{}},text:async()=> 'Access denied'}),alert(){}};
vm.createContext(context);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),context);
(async()=>{
 buttons[6].onclick();await new Promise(setImmediate);
 assert.equal(elements['#diagnosticsTab'].hidden,false);
 assert.equal(elements['#webTab'].hidden,true);
 assert.equal(elements['#diagnosticsEnabled'].checked,true);
 fail=true;buttons[6].onclick();await new Promise(setImmediate);
 assert.equal(elements['#diagnosticsStatus'].textContent,'Access denied');
 buttons[0].onclick();assert.equal(elements['#diagnosticsTab'].hidden,true);
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result = subprocess.run(['node', '-e', script, str(ROOT / 'app/static/admin.js')],
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr


@pytest.fixture
def diagnostic_api(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app import main, auth, diagnostic_bundle as diag
    monkeypatch.setattr(diag, 'BASE', tmp_path / 'diagnostics')
    monkeypatch.delenv('MTA_DIAGNOSTICS_ENABLED', raising=False)
    monkeypatch.setattr(main.ai_arranger_runtime, 'list_jobs', lambda *_: [])
    monkeypatch.setattr(main.ai_arranger_runtime, '_limit', lambda: 1)
    identity = {'user': None}
    monkeypatch.setattr(auth, 'session_user', lambda request: identity['user'])
    monkeypatch.setattr(main, 'session_user', lambda request: identity['user'])
    return TestClient(main.app), identity


def test_diagnostics_authorization_enable_create_download(diagnostic_api):
    client, identity = diagnostic_api
    base = '/api/admin/diagnostics'
    headers = {'x-mta-request': '1'}
    for role, code in ((None, 401), ('user', 403)):
        identity['user'] = {'role': role} if role else None
        assert client.get(base + '/settings').status_code == code
        assert client.put(base + '/settings', json={'enabled': True}, headers=headers).status_code == code
        assert client.post(base + '/bundles', headers=headers).status_code == code
        assert client.get(base + '/bundles/mta-diagnostics-' + 'a'*32 + '.zip').status_code == code
    identity['user'] = {'role': 'admin'}
    assert client.get('/settings').status_code == 200
    assert client.get(base + '/settings').json()['enabled'] is False
    assert client.post(base + '/bundles', headers=headers).status_code == 403
    assert client.put(base + '/settings', json={'enabled': True}).status_code == 403
    assert client.put(base + '/settings', json={'enabled': 'yes'}, headers=headers).status_code == 400
    assert client.put(base + '/settings', json={'enabled': True}, headers=headers).json()['enabled']
    response = client.post(base + '/bundles', headers=headers)
    assert response.status_code == 200, response.text
    download = client.get(response.json()['url'])
    assert download.status_code == 200
    assert download.headers['cache-control'] == 'no-store'
    with zipfile.ZipFile(io.BytesIO(download.content)) as bundle:
        assert json.loads(bundle.read('diagnostics.json'))['status']['ai_queue']['jobs'] == []
    assert not client.put(base + '/settings', json={'enabled': False}, headers=headers).json()['enabled']
    assert client.get(response.json()['url']).status_code == 403


def test_worker_failure_classification_in_bundle_without_stderr(tmp_path, monkeypatch):
    from app import diagnostic_bundle as diag
    from app.ai_cgroup_metering import _worker_failure
    monkeypatch.setattr(diag, 'BASE', tmp_path)
    diag.configure(True)
    record = logging.LogRecord('app.ai_cgroup_metering', logging.ERROR, __file__, 1,
                              'sensitive user prompt', (), None)
    record.mta_worker_failure = _worker_failure('ACE-Step adapter error: Connection refused token=PRIVATE', 1)
    diag.SafeEvents().emit(record)
    with zipfile.ZipFile(diag.create({})) as bundle:
        event = json.loads(bundle.read('events.jsonl'))
        assert event['worker_failure']['category'] == 'ace_connection_refused'
        assert event['worker_failure']['metering_valid'] is False
        assert b'PRIVATE' not in bundle.read('events.jsonl')
        assert b'sensitive' not in bundle.read('events.jsonl')


def test_diagnostic_logging_never_breaks_worker_when_directory_unavailable(monkeypatch):
    from app import diagnostic_bundle as diag
    monkeypatch.setattr(diag, 'enabled', lambda: (_ for _ in ()).throw(PermissionError('denied')))
    diag.SafeEvents().emit(logging.LogRecord('test', logging.ERROR, __file__, 1, 'failure', (), None))
