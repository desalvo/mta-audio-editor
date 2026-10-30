"""Read-only installed application diagnostics must be portable and report errors."""
import json
from pathlib import Path
import plistlib
import subprocess
import sys
import zipfile

import pytest
from scripts import installed_diagnostics_r208 as diagnostics

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'scripts'/'installed_diagnostics_r208.py'


def invoke(tmp_path,mode,*extra):
    out=tmp_path/'out'
    result=subprocess.run([sys.executable,str(SCRIPT),'--mode',mode,'--output',str(out),*map(str,extra)],capture_output=True,text=True,timeout=25)
    report=json.loads((out/'report.json').read_text())
    z=out/('mta-r208-'+mode+'-diagnostics.zip')
    with zipfile.ZipFile(z) as bundle:
        assert bundle.namelist()==['report.json','report.md']
        assert bundle.testzip() is None
    return result,report


def test_linux_installed_executable(tmp_path):
    exe=tmp_path/'mta-audio-editor'
    exe.write_text('#!/bin/sh\nexit 0\n');exe.chmod(0o755)
    p,report=invoke(tmp_path,'linux','--app',exe)
    assert p.returncode==0
    assert any(c['name']=='executable_access' and c['status']=='PASS' for c in report['checks'])


def test_windows_installed_executable_without_powershell(tmp_path, monkeypatch):
    monkeypatch.setenv('PATH', str(tmp_path/'empty-path'))
    exe=tmp_path/'MTA Audio Editor.exe'
    exe.write_bytes(b'MZ'+b'0'*8192)
    p,report=invoke(tmp_path,'windows','--app',exe)
    assert p.returncode==0
    assert any(c['name']=='executable_signature' and c['status']=='PASS' for c in report['checks'])


@pytest.mark.skipif(sys.platform == 'win32', reason='Foreign-host CLI regression')
@pytest.mark.parametrize('shell', ['pwsh', 'powershell'])
def test_windows_inspection_does_not_run_foreign_host_powershell(tmp_path, monkeypatch, shell):
    exe = tmp_path/'MTA Audio Editor.exe'
    exe.write_bytes(b'MZ'+b'0'*8192)
    marker = tmp_path/'shell-started'
    command = tmp_path/shell
    command.write_text('#!/bin/sh\n: > "'+str(marker)+'"\nexit 42\n')
    command.chmod(0o755)
    monkeypatch.setenv('PATH', str(tmp_path))
    result, report = invoke(tmp_path, 'windows', '--app', exe)
    assert result.returncode == 0
    assert any(c['name'] == 'host_platform' and c['status'] == 'WARN' for c in report['checks'])
    assert any(c['name'] == 'authenticode' and c['status'] == 'SKIP' for c in report['checks'])
    assert not marker.exists()


@pytest.mark.parametrize('response,status', [({'exit_code': 0, 'output': 'Valid\n'}, 'PASS'),
                                           ({'error': 'TimeoutExpired'}, 'WARN')])
def test_windows_host_retains_bounded_authenticode_check(tmp_path, monkeypatch, response, status):
    exe = tmp_path/'MTA Audio Editor.exe'
    exe.write_bytes(b'MZ'+b'0'*8192)
    monkeypatch.setattr(diagnostics.platform, 'system', lambda: 'Windows')
    monkeypatch.setattr(diagnostics.shutil, 'which', lambda name: 'pwsh' if name == 'pwsh' else None)
    monkeypatch.setenv('MTA_DIAGNOSTIC_TARGET', 'original-value')
    calls = []
    def run(argv, timeout):
        import os
        calls.append((argv, timeout, os.environ['MTA_DIAGNOSTIC_TARGET']))
        return response
    monkeypatch.setattr(diagnostics, 'run_command', run)
    checks = []
    diagnostics.inspect_windows(checks, exe)
    assert len(calls) == 1 and calls[0][1:] == (25, str(exe))
    assert calls[0][0][:3] == ['pwsh', '-NoProfile', '-Command']
    assert any(c['name'] == 'authenticode' and c['status'] == status for c in checks)
    import os
    assert os.environ['MTA_DIAGNOSTIC_TARGET'] == 'original-value'


def test_macos_bundle_metadata(tmp_path):
    app=tmp_path/'MTA Audio Editor.app';(app/'Contents/MacOS').mkdir(parents=True)
    (app/'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier':'eu.test.mta','CFBundleExecutable':'mta','CFBundleShortVersionString':'0.3.0'}))
    exe=app/'Contents/MacOS/mta';exe.write_text('#!/bin/sh\nexit 0\n');exe.chmod(0o755)
    p,report=invoke(tmp_path,'macos','--app',app)
    assert p.returncode==0
    assert any(c['name']=='bundle_executable' and c['status']=='PASS' for c in report['checks'])


def test_server_unreachable_fails_but_emits_archive(tmp_path):
    p,report=invoke(tmp_path,'server','--url','http://127.0.0.1:1')
    assert p.returncode==1
    assert report['status']=='FAIL'
    assert all(c['status']=='FAIL' for c in report['checks'] if c['name'].startswith('/'))
