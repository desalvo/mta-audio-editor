"""Same-revision desktop Early updates compare the selected package's build."""
import ast
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest
from native import update_manager as updater


@pytest.fixture
def early(monkeypatch):
    release = {'name': 'MTA Audio Editor Early Release', 'assets': []}
    manifest = {'version': '0.3.0', 'revision': '210', 'release': '0.3.0-r210'}
    monkeypatch.setattr(updater, 'sys_platform', lambda: 'darwin')
    monkeypatch.setattr(updater.platform, 'machine', lambda: 'arm64')
    monkeypatch.setattr(updater, '_get_json', lambda url: manifest if url.endswith('early-update.json') else release)
    release['assets'].append({'name': 'early-update.json', 'browser_download_url': 'https://example.invalid/early-update.json'})
    return release, manifest


def asset(build='20261017210000', revision=210, platform='macOS-arm64', date='2026-10-17T19:00:00Z'):
    suffix = '.exe' if 'Windows' in platform else '.dmg'
    name = f'MTA-Audio-Editor-0.3.0-r{revision}-b{build}-{platform}{suffix}'
    return {'name': name, 'browser_download_url': 'https://example.invalid/' + name, 'created_at': date}


@pytest.mark.parametrize('remote,expected', [('20261017210000', True), ('20261017200000', False), ('20261017190000', False)])
def test_same_revision_compares_build(early, remote, expected):
    release, _ = early; release['assets'].append(asset(remote))
    info = updater.check_for_update('0.3.0-r210', 'early', current_build='20261017200000')
    assert info['available'] is expected
    assert info['latest_build'] == remote and info['current_build'] == '20261017200000'
    assert remote in info['latest_display'] and '20261017200000' in info['current_display']


def test_windows_build_discovery(early, monkeypatch):
    release, _ = early; release['assets'].append(asset(platform='Windows-x64-Setup'))
    monkeypatch.setattr(updater.os, 'name', 'nt')
    assert updater.check_for_update('0.3.0-r210', 'early', current_build='20261017200000')['available']


def test_other_architecture_newer_build_does_not_trigger_update(early):
    release, _ = early
    release['assets'] += [asset('20261017190000'), asset('20261017220000', platform='macOS-x64')]
    info = updater.check_for_update('0.3.0-r210', 'early', current_build='20261017200000')
    assert not info['available'] and 'arm64' in info['asset_name']


def test_stale_platform_revision_does_not_inherit_global_manifest(early):
    release, manifest = early
    manifest['release'] = '0.3.0-r211'
    release['assets'] += [asset(revision=209), asset(revision=211, platform='macOS-x64')]
    info = updater.check_for_update('0.3.0-r210', 'early', current_build='20261017100000')
    assert not info['available'] and info['latest_version'] == '0.3.0-r209'


def test_newer_revision_wins_over_older_build(early):
    release, _ = early; release['assets'].append(asset('20261017100000', revision=211))
    assert updater.check_for_update('0.3.0-r210', 'early', current_build='20261017200000')['available']


def test_manifest_failure_still_compares_build_from_installer(early, monkeypatch):
    release, _ = early; release['assets'].append(asset())
    def fetch(url):
        if url.endswith('early-update.json'): raise OSError('fixture unavailable')
        return release
    monkeypatch.setattr(updater, '_get_json', fetch)
    assert updater.check_for_update('0.3.0-r210', 'early', current_build='20261017200000')['available']


def test_exact_package_manifest_build_fallback(early):
    release, manifest = early
    name = 'MTA-Audio-Editor-0.3.0-r210-macOS-arm64.dmg'
    release['assets'].append({'name': name})
    manifest['package_builds'] = {name: '20261017210000', 'other-platform': '20261017230000'}
    assert updater.check_for_update('0.3.0-r210', 'early', current_build='20261017200000')['available']


@pytest.mark.parametrize('current', ['', 'unknown', '20261317200000'])
def test_unknown_local_build_cannot_create_repeated_update(early, current):
    release, _ = early; release['assets'].append(asset())
    assert not updater.check_for_update('0.3.0-r210', 'early', current_build=current)['available']


def test_stable_comparison_ignores_rebuild(early):
    release, _ = early; release['name'] = 'MTA Audio Editor 0.3.0-r210'
    release['assets'].append(asset())
    assert not updater.check_for_update('0.3.0-r210', 'stable', current_build='20261017200000')['available']


def test_early_requires_an_installable_package(early):
    release, _ = early; release['assets'].append(asset(revision=211, platform='macOS-x64'))
    assert not updater.check_for_update('0.3.0-r210', 'early', current_build='20261017200000')['available']


def test_asset_build_order_and_exact_revision_match(early):
    release, _ = early
    release['assets'] += [asset('20261017210000', date='2026-10-17T18:00:00Z'),
        asset('20261017200000', date='2026-10-17T20:00:00Z'), asset(revision=21)]
    chosen = updater.choose_asset(release['assets'], '0.3.0-r210')
    assert 'b20261017210000' in chosen['name']
    assert '-r21-' in updater.choose_asset(release['assets'], '0.3.0-r21')['name']


def test_publication_manifest_uses_each_actual_installer_build(tmp_path):
    from scripts.build_early_update_manifest import build_manifest
    for platform, build in [('Windows-x64-Setup', '20261017210000'), ('macOS-arm64', '20261017220000')]:
        (tmp_path / asset(build, platform=platform)['name']).write_bytes(b'fixture')
    doc = build_manifest(tmp_path, '0.3.0', '210')
    assert sorted(doc['package_builds'].values()) == ['20261017210000', '20261017220000']
    (tmp_path / 'MTA-Audio-Editor-0.3.0-r210-macOS-x64.dmg').write_bytes(b'legacy')
    with pytest.raises(ValueError, match='identity'): build_manifest(tmp_path, '0.3.0', '210')


def test_native_bridge_passes_installed_build(monkeypatch):
    import app.version
    captured = []
    monkeypatch.setattr(updater, 'check_for_update', lambda *a, **kw: captured.append((a, kw)) or {})
    tree = ast.parse(Path('native/mta_audio_editor_native.py').read_text())
    node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'check_for_updates')
    module = ast.Module(body=[node], type_ignores=[]); namespace = {}
    exec(compile(module, '<bridge>', 'exec'), namespace)  # noqa: S102 -- trusted local bridge AST
    namespace['check_for_updates'](SimpleNamespace(get_native_settings=lambda: {'update_channel': 'early'}))
    assert captured == [((app.version.APP_RELEASE, 'early'), {'current_build': app.version.BUILD_ID})]


def test_update_dialog_shows_both_builds():
    source = Path('app/static/app.js').read_text()
    section = source[source.index('async function checkNativeAppUpdate('):source.index('async function installNativeAppUpdate(')]
    script = r'''
const vm=require('vm'),assert=require('assert');let html;
const ctx={currentUser:{native_single_user:true},waitForNativeApi:async()=>({check_for_updates:async()=>({ok:true,available:true,channel:'early',latest_version:'0.3.0-r210',current_version:'0.3.0-r210',latest_display:'0.3.0-r210 · build 20261017210000',current_display:'0.3.0-r210 · build 20261017200000'})}),esc:s=>s||'',showUtilityModal:(title,body)=>html=body,toast:x=>{throw Error(x)}};
vm.createContext(ctx);vm.runInContext(process.argv[1],ctx);ctx.checkNativeAppUpdate(true).then(()=>{assert.ok(html.includes('20261017210000'));assert.ok(html.includes('20261017200000'))}).catch(e=>{console.error(e);process.exitCode=1});
'''
    result = subprocess.run(['node', '-e', script, section], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


def test_ci_build_identity_is_stamped_per_desktop_installer():
    workflow = Path('.github/workflows/ci-cd.yml').read_text()
    assert '/DMyAppBuildSuffix=$buildSuffix' in workflow
    assert 'r${revision}${build_suffix}-macOS-' in workflow
    assert 'python scripts/build_early_update_manifest.py early-assets' in workflow
    assert 'early' in workflow[workflow.index('$buildSuffix ='):workflow.index('$buildSuffix =') + 150]
