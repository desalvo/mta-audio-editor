"""Reproduce clean-import and offline-source failures from the RPM/Quality logs."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shlex
import shutil
import socket
import sys

import pytest
import yaml

ROOT=Path(__file__).resolve().parents[1]


def display_builder():
    spec=importlib.util.spec_from_file_location('ci_display_builder',ROOT/'scripts/build_server_display.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_default_display_build_uses_verified_local_source_without_network(tmp_path,monkeypatch):
    builder=display_builder();calls=[]
    def no_network(*args,**kwargs):pytest.fail('Private display build attempted network I/O')
    monkeypatch.setattr(socket,'create_connection',no_network)
    def meson(cmd,**kwargs):
        calls.append(cmd)
        if 'install' in cmd:
            binary=Path(cmd[cmd.index('--destdir')+1])/'usr/bin/Xvfb'
            binary.parent.mkdir(parents=True);binary.write_bytes(b'target-built-display')
    monkeypatch.setattr(builder.subprocess,'run',meson)
    binary=builder.build(tmp_path/'output')
    record=json.loads((binary.parent/'display-build.json').read_text())
    assert record['source_sha256']==builder.SHA256
    assert record['binary_sha256']==hashlib.sha256(binary.read_bytes()).hexdigest()
    assert (binary.parent/'XSERVER-COPYING').read_bytes()==(builder.SOURCE_ARCHIVE.parent/'XSERVER-COPYING').read_bytes()
    assert len(calls)==3 and 'setup' in calls[0] and 'Xvfb' in calls[1] and '--no-rebuild' in calls[2]


@pytest.mark.parametrize('via_env',[False,True])
def test_source_override_cannot_bypass_digest(tmp_path,monkeypatch,via_env):
    builder=display_builder();archive=tmp_path/'unsafe.tar.xz';archive.write_bytes(b'not-the-reviewed-source')
    monkeypatch.setattr(builder.subprocess,'run',lambda *a,**k:pytest.fail('Invalid source reached compiler'))
    if via_env:monkeypatch.setenv('MTA_XSERVER_SOURCE_ARCHIVE',str(archive))
    with pytest.raises(ValueError,match='checksum mismatch'):
        builder.build(tmp_path/'out',None if via_env else archive)


def test_missing_local_source_is_explicit(tmp_path):
    with pytest.raises(ValueError,match='Missing pinned X.Org source archive'):
        display_builder().build(tmp_path/'out',tmp_path/'absent')


def test_clean_runtime_install_resolves_numpy_before_abi_check(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    import build_vst3_runtime as runtime
    installed=set();calls=[]
    def pip(cmd,**kwargs):
        calls.append(cmd)
        if cmd[-1]=='numpy':
            assert '--upgrade' not in cmd and '--force-reinstall' not in cmd
            installed.add('numpy')
        elif '-c' in cmd:
            if 'numpy' not in installed:raise ModuleNotFoundError('numpy')
            assert '_mta_process_sidechain' in cmd[-1] and '_mta_set_musical_position' in cmd[-1]
        else:assert '--no-deps' in cmd and '--force-reinstall' in cmd
    monkeypatch.setattr(runtime.subprocess,'run',pip)
    runtime.install_wheel('compiled-host.whl')
    assert len(calls)==3 and calls[0][:3]==[sys.executable,'-m','pip']


def test_rpm_build_and_runtime_have_atomic_dependency():
    workflow=yaml.safe_load((ROOT/'.github/workflows/server-native-runtime-validation.yml').read_text())
    for name in ('rpm-payload','el10-rpm-native'):
        job=workflow['jobs'][name]
        assert any('gcc-c++ libatomic ' in s.get('run','') for s in job['steps'])
    requires=next(l for l in (ROOT/'scripts/server_packages/build_rpm.sh').read_text().splitlines() if l.startswith('Requires:'))
    assert 'libatomic' in requires.split(', ')
    assert 'libatomic1' in (ROOT/'scripts/server_packages/build_deb.sh').read_text()


def test_strict_native_audit_keeps_alsa_jack_metadata_prerequisites():
    workflow=yaml.safe_load((ROOT/'.github/workflows/ci-cd.yml').read_text())
    steps=workflow['jobs']['security']['steps']
    script=next(s['run'] for s in steps if s.get('name')=='Python dependency audit')
    assert script.index('libasound2-dev libjack-jackd2-dev')<script.index('pip-audit -r requirements-native.txt --strict')
    assert '--ignore-vuln' not in script and '--disable-pip' not in script


def test_quality_plugin_fixture_does_not_enter_source_archive(tmp_path):
    from scripts.license_gate import audit
    workflow=yaml.safe_load((ROOT/'.github/workflows/ci-cd.yml').read_text())
    steps=workflow['jobs']['quality']['steps']
    workspace=tmp_path/'checkout';workspace.mkdir()
    (workspace/'docs').mkdir()
    shutil.copy2(ROOT/'docs/THIRD_PARTY_NOTICES.md',workspace/'docs/THIRD_PARTY_NOTICES.md')
    runner=tmp_path/'runner-temp';runner.mkdir()
    fetch=next(s for s in steps if s.get('name')=='Fetch hash-pinned live VST3 test effect')
    destination=Path(shlex.split(fetch['run'])[-1].replace('$RUNNER_TEMP',str(runner)))
    if not destination.is_absolute():destination=workspace/destination
    plugin=destination/'CHOWTapeModel.vst3'
    binary=plugin/'Contents/x86_64-linux/CHOWTapeModel.so'
    binary.parent.mkdir(parents=True);binary.write_bytes(b'ci-fixture-only')
    env=next(s for s in steps if s.get('name')=='Unit tests and coverage gate')['env']
    configured=env['MTA_TEST_LIVE_VST3'].replace('${{ runner.temp }}',str(runner)).replace('${{ github.workspace }}',str(workspace))
    assert Path(configured).resolve()==plugin.resolve()
    # This is the actual source audit that failed on the CI fixture. The old
    # checkout-relative workflow makes it fail, without weakening the guard.
    result=audit(workspace)
    assert result['ok'],result['errors']
    shutil.copytree(plugin,workspace/'.external/unreviewed.vst3')
    assert not audit(workspace)['ok']
