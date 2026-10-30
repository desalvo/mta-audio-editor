from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_wizard_configures_trusted_worker_for_local_remote_and_disabled():
    text = (ROOT / 'scripts/install_mta_native_wizard.sh').read_text()
    assert text.count('set_setting MTA_AI_WORKER_ENABLED true') == 2
    assert 'set_setting MTA_AI_WORKER_ENABLED false' in text
    assert text.count('set_setting MTA_AI_WORKER_EXECUTABLE "$worker"') == 2
    assert '/usr/lib/mta-audio-editor-server/app/ace_step_http_worker.py' in text


def test_server_payload_executable_for_rpm_and_deb():
    for name in ('build_rpm.sh', 'build_deb.sh'):
        text = (ROOT / 'scripts/server_packages' / name).read_text()
        assert 'chmod 755' in text and 'ace_step_http_worker.py' in text


def test_catalog_reports_configured_worker_not_static_disabled(monkeypatch, tmp_path):
    from app.ai_arranger import catalog
    worker = tmp_path / 'worker'
    worker.write_text('#!/bin/sh\nexit 0\n')
    worker.chmod(0o755)
    monkeypatch.setenv('MTA_AI_WORKER_ENABLED', 'true')
    monkeypatch.setenv('MTA_AI_WORKER_EXECUTABLE', str(worker))
    entry = next(x for x in catalog()['models'] if x['id'] == 'ace-step-1.5')
    # A script that exits successfully is not an installed ACE model adapter.
    assert entry['available'] is False
    monkeypatch.setenv('MTA_AI_WORKER_ENABLED', 'false')
    entry = next(x for x in catalog()['models'] if x['id'] == 'ace-step-1.5')
    assert entry['available'] is False
