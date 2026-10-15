"""Read-only installed application diagnostics must be portable and report errors."""
import json
from pathlib import Path
import plistlib
import subprocess
import sys
import zipfile

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


def test_windows_installed_executable_without_powershell(tmp_path):
    exe=tmp_path/'MTA Audio Editor.exe'
    exe.write_bytes(b'MZ'+b'0'*8192)
    p,report=invoke(tmp_path,'windows','--app',exe)
    assert p.returncode==0
    assert any(c['name']=='executable_signature' and c['status']=='PASS' for c in report['checks'])


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
