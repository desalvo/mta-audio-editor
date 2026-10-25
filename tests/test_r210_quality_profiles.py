"""Quality selection preserves the full tree and makes deferred browser scope explicit."""
import importlib.util
import json
from pathlib import Path

import yaml

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('quality_runner',ROOT/'scripts/run_quality_tests.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)


def test_partition_is_disjoint_exhaustive_and_preserves_security_checks():
    unit,browser=runner.suites(ROOT)
    assert not set(unit)&set(browser)
    paths=set((ROOT/'tests').rglob('test_*.py'))|set((ROOT/'tests').rglob('*_test.py'))
    assert set(unit)|set(browser)=={p.relative_to(ROOT).as_posix() for p in paths}
    assert 'tests/test_r210_pull_lifecycle.py' in unit
    assert 'tests/test_r210_remote_transport_inventory.py' in unit
    assert 'tests/test_r210_paypal_merchant_history_browser.py' in browser


def test_ast_classifier_includes_nested_and_optional_browser_imports(tmp_path):
    tests=tmp_path/'tests';tests.mkdir()
    samples={'unit':'def test_api(): pass',
             'browser':'def test_ui():\n from playwright.sync_api import sync_playwright',
             'optional':'import pytest\napi=pytest.importorskip("playwright.sync_api")'}
    for name,text in samples.items():(tests/f'test_{name}.py').write_text(text)
    nested=tests/'nested';nested.mkdir();(nested/'extra_test.py').write_text('def test_nested(): pass')
    unit,browser=runner.suites(tmp_path)
    assert unit==['tests/nested/extra_test.py','tests/test_unit.py']
    assert set(browser)=={'tests/test_browser.py','tests/test_optional.py'}


def test_ci_runner_records_selection_forwards_failure_and_disables_auth_bypass(tmp_path,monkeypatch):
    script=tmp_path/'scripts/run_quality_tests.py';script.parent.mkdir();script.write_text('')
    tests=tmp_path/'tests';tests.mkdir()
    (tests/'test_api.py').write_text('def test_api(): pass')
    (tests/'test_ui.py').write_text('import playwright.sync_api')
    monkeypatch.setattr(runner,'__file__',str(script))
    monkeypatch.setenv('MTA_ALLOW_INSECURE_NO_AUTH','true')
    seen=[]
    def call(command,**kwargs):
        seen.append(command)
        assert kwargs['env']['MTA_ALLOW_INSECURE_NO_AUTH']=='false'
        assert kwargs['env']['MTA_TEST_OFFLINE']=='1'
        return 7
    monkeypatch.setattr(runner.subprocess,'call',call)
    assert runner.main(['--suite','unit','--','--cov-fail-under=70'])==7
    report=json.loads((tmp_path/'quality-test-selection.json').read_text())
    assert report['deferred']==['tests/test_ui.py'] and not report['complete_regression']
    assert seen[-1][-1]=='tests/test_api.py' and '--cov-fail-under=70' in seen[-1]
    assert runner.main(['--suite','full'])==7
    report=json.loads((tmp_path/'quality-test-selection.json').read_text())
    assert report['complete_regression'] and not report['deferred']
    assert seen[-1][-2:]==['tests/test_api.py','tests/test_ui.py']


def test_full_regression_is_manual_opt_in_and_automatic_on_release_tags():
    config=yaml.safe_load((ROOT/'.github/workflows/ci-cd.yml').read_text())
    events=config.get('on',config.get(True))
    assert events['workflow_dispatch']['inputs']['full_validation']['default'] is False
    steps=config['jobs']['quality']['steps']
    scope=next(s for s in steps if s.get('id')=='quality_scope')
    browser=next(s for s in steps if s.get('name')=='Prepare real browser server VST3 regression')
    tests=next(s for s in steps if s.get('name')=='Unit tests and coverage gate')
    assert 'steps.quality_scope.outputs.full_validation' in browser['if']
    assert 'refs/tags/v' in scope['env']['FULL_VALIDATION']
    assert 'inputs.full_validation == true' in scope['env']['FULL_VALIDATION']
    assert '[full-ci]' in scope['env']['FULL_VALIDATION']
    assert 'steps.quality_scope.outputs.suite' in tests['env']['MTA_TEST_SUITE']
    assert tests['env']['MTA_ALLOW_INSECURE_NO_AUTH']=='false'
    assert '--cov-fail-under=70' in tests['run']
    for name in ('publish','early-release'):
        assert 'quality' in config['jobs'][name]['needs']
        assert "needs.quality.outputs.full_validation == 'true'" in config['jobs'][name]['if']
