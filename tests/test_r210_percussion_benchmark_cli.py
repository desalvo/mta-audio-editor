"""Local CLI cannot dispatch inference or grant professional approval."""
import json

import pytest

from app import auth, percussion_adapters, percussion_benchmark as benchmark, service_admission
from app.percussion_benchmark_cli import main


@pytest.fixture
def cli_data(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, 'DATA_ROOT', tmp_path / 'data')
    return auth.DATA_ROOT


@pytest.fixture(autouse=True)
def isolated_cli_data(cli_data):
    """Every CLI test owns its local journal root; no production data touched."""
    return cli_data


@pytest.fixture
def no_inference(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Read/prepare/report CLI must not dispatch neural inference')
    monkeypatch.setattr(percussion_adapters, 'infer', forbidden)
    monkeypatch.setattr(benchmark, 'run', forbidden)
    monkeypatch.setattr(benchmark, 'start', forbidden)
    monkeypatch.setattr(benchmark, 'approve', forbidden)


@pytest.mark.parametrize('command,method', [('prepare', 'prepare_synthetic'), ('catalog', 'catalog'), ('list', 'campaigns')])
def test_read_and_prepare_commands_only_call_the_corresponding_operation(monkeypatch, capsys, no_inference, command, method):
    monkeypatch.setattr(benchmark, method, lambda: {'operation': command})
    assert main([command]) == 0
    assert json.loads(capsys.readouterr().out) == {'operation': command}


@pytest.mark.parametrize('command,method', [('show', 'get'), ('reports', 'reports')])
def test_campaign_inspection_is_explicit(monkeypatch, capsys, no_inference, command, method):
    monkeypatch.setattr(benchmark, method, lambda cid: {'campaign': cid})
    assert main([command, 'fixture-id']) == 0
    assert json.loads(capsys.readouterr().out) == {'campaign': 'fixture-id'}


def test_export_never_overwrites_a_previous_package(tmp_path, monkeypatch, capsys, no_inference):
    package = tmp_path / 'campaign.zip'
    monkeypatch.setattr(benchmark, 'export', lambda cid: b'package fixture')
    assert main(['export', 'fixture', '--output', str(package)]) == 0
    assert package.read_bytes() == b'package fixture'
    capsys.readouterr()
    monkeypatch.setattr(benchmark, 'export', lambda cid: b'replacement')
    assert main(['export', 'fixture', '--output', str(package)]) == 1
    assert package.read_bytes() == b'package fixture'


@pytest.mark.parametrize('action', ['run', 'infer', 'approve', 'create'])
def test_cli_has_no_unowned_execution_or_approval_path(no_inference, action):
    with pytest.raises(SystemExit) as result:
        main([action])
    assert result.value.code == 2


def test_explicit_local_root_cannot_be_relative_or_symbolic(tmp_path, no_inference):
    with pytest.raises(SystemExit):
        main(['--data-root', '../somewhere', 'catalog'])
    link = tmp_path / 'linked'; link.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(SystemExit):
        main(['--data-root', str(link), 'catalog'])


def test_actual_drain_rejects_selected_root_before_any_benchmark_effect(tmp_path, monkeypatch, capsys, no_inference):
    selected = tmp_path / 'selected-service'
    monkeypatch.setattr(auth, 'DATA_ROOT', selected)
    monkeypatch.setenv('MTA_SERVICE_ADMISSION', service_admission.MODE)
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER', 'false')
    monkeypatch.setenv('MTA_ADMIN_PASSWORD', 'administrator-password')
    auth.init_auth_db()
    actor = auth.find_user('admin')['id']
    with service_admission.operation('cli-drain-fixture'):
        pass
    service_admission.change(actor=actor, expected_generation=0, draining=True,
                             identifier='cli-drain', confirm=True)
    # Main must select the requested authority before checking its admission;
    # the unrelated default root deliberately has no admission journal.
    monkeypatch.setattr(auth, 'DATA_ROOT', tmp_path / 'unrelated-default')
    invoked = []
    monkeypatch.setattr(benchmark, 'prepare_synthetic', lambda: invoked.append('forbidden-effect'))
    assert main(['--data-root', str(selected), 'prepare']) == 1
    assert not invoked and not (selected / 'ai-benchmarks').exists()
    assert 'draining' in capsys.readouterr().err.lower()
