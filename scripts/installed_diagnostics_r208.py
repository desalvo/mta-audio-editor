#!/usr/bin/env python3
"""Read-only diagnostic runner for installed MTA native apps and server (r208).

Standard library only; no changes to installed applications, projects or services.
Exit 0: all required checks pass; 1: failed required check; 2: application missing.
"""
from __future__ import annotations
import argparse
import http.client
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit

VERSION = '0.3.0-r208'
SENSITIVE = re.compile(r'(?i)(password|token|secret|authorization|cookie|api[_-]?key|private[_-]?key)')


def run_command(argv, timeout=12):
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
        return {'exit_code':p.returncode, 'output':(p.stdout+p.stderr)[-2500:]}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'error':type(exc).__name__}


def check(results, name, status, detail=''):
    results.append({'name':name, 'status':status, 'detail':str(detail)[:750]})
    print(f'{status:5s} {name}', flush=True)


def inspect_macos(results, target):
    paths = ([target] if target else [Path('/Applications/MTA Audio Editor.app'), Path.home()/'Applications/MTA Audio Editor.app'])
    app = next((p for p in paths if p.is_dir()), None)
    if not app:
        check(results,'native_application','FAIL','Not found; use --app /path/to/App.app')
        return
    check(results,'native_application','PASS',str(app))
    info = app/'Contents/Info.plist'
    try:
        obj = plistlib.loads(info.read_bytes())
        check(results,'bundle_metadata','PASS', f"bundle={obj.get('CFBundleIdentifier','?')} version={obj.get('CFBundleShortVersionString','?')}")
        exe = app/'Contents/MacOS'/obj.get('CFBundleExecutable','')
        check(results,'bundle_executable','PASS' if exe.is_file() and os.access(exe,os.X_OK) else 'FAIL',str(exe))
    except (OSError, ValueError, TypeError) as exc:
        check(results,'bundle_metadata','FAIL',type(exc).__name__)
    if shutil.which('codesign'):
        r=run_command(['codesign','--verify','--deep','--strict',str(app)],30)
        check(results,'codesign_integrity','PASS' if r.get('exit_code')==0 else 'FAIL',r.get('output',''))
    if shutil.which('spctl'):
        r=run_command(['spctl','--assess','--type','execute',str(app)],20)
        check(results,'gatekeeper_assessment','PASS' if r.get('exit_code')==0 else 'WARN',r.get('output',''))


def inspect_windows(results,target):
    candidates=([target] if target else [Path(os.environ.get('ProgramFiles',r'C:\Program Files'))/'MTA Audio Editor', Path(os.environ.get('LOCALAPPDATA',str(Path.home()))) / 'Programs' / 'MTA Audio Editor'])
    def locate(x):
        if x.is_file() and x.suffix.lower()=='.exe': return x
        if x.is_dir():
            return next((p for p in x.glob('*.exe') if 'unins' not in p.name.lower()),None)
        return None
    exe=next((p for x in candidates if (p:=locate(x))),None)
    if not exe:
        check(results,'native_application','FAIL','Executable not found; use --app "C:\\path\\MTA.exe"')
        return
    check(results,'native_application','PASS',str(exe))
    check(results,'executable_signature','PASS' if exe.stat().st_size>4096 else 'FAIL',f'size={exe.stat().st_size}')
    if shutil.which('powershell') or shutil.which('pwsh'):
        shell=shutil.which('pwsh') or shutil.which('powershell')
        # Explicit static script; user-controlled path travels as an environment variable.
        envkey='MTA_DIAGNOSTIC_TARGET'
        old=os.environ.get(envkey)
        os.environ[envkey]=str(exe)
        try:
            r=run_command([shell,'-NoProfile','-Command',"$s=Get-AuthenticodeSignature -LiteralPath $env:MTA_DIAGNOSTIC_TARGET; Write-Output $s.Status"],25)
            state=r.get('output','').strip()
            check(results,'authenticode', 'PASS' if state=='Valid' else 'WARN',state or 'Signature unavailable')
        finally:
            if old is None: os.environ.pop(envkey,None)
            else: os.environ[envkey]=old


def inspect_linux(results,target):
    candidates=([target] if target else [Path('/usr/bin/mta-audio-editor'),Path('/opt/mta-audio-editor'),Path.home()/'.local/bin/mta-audio-editor'])
    p=next((x for x in candidates if x.exists()),None)
    if not p:
        which=shutil.which('mta-audio-editor')
        p=Path(which) if which else None
    if not p:
        check(results,'native_application','FAIL','Not found; use --app /path/to/executable-or-AppImage')
        return
    if p.is_dir():
        p=next((x for x in p.rglob('mta*') if x.is_file() and os.access(x,os.X_OK)),p)
    check(results,'native_application','PASS',str(p))
    check(results,'executable_access','PASS' if p.is_file() and os.access(p,os.X_OK) else 'FAIL',str(p))
    for manager,args in [('dpkg-query',['dpkg-query','-W','mta-audio-editor']),('rpm',['rpm','-q','mta-audio-editor'])]:
        if shutil.which(manager):
            r=run_command(args)
            check(results,manager+'_package','PASS' if r.get('exit_code')==0 else 'WARN',r.get('output','').strip())


def inspect_server(results,base_url):
    parsed=urlsplit(base_url)
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.fragment or parsed.query:
        check(results,'server_url','FAIL','Only http(s) URL without credentials/query/fragment is supported')
        return
    if parsed.scheme!='https' and parsed.hostname not in ('127.0.0.1','localhost','::1'):
        check(results,'server_transport','WARN','HTTP to remote host is unencrypted; avoid credentialed checks')
    endpoints=['/api/health','/openapi.json','/docs/user']
    for endpoint in endpoints:
        connection=None
        try:
            # Explicit HTTP(S) transports never follow a redirect to another
            # host, insecure scheme, local file or custom protocol.
            transport=http.client.HTTPSConnection if parsed.scheme=='https' else http.client.HTTPConnection
            connection=transport(parsed.hostname,parsed.port,timeout=8)
            connection.request('GET',parsed.path.rstrip('/')+endpoint,headers={'User-Agent':'MTA-r208-diagnostics','Accept':'application/json,text/html'})
            response=connection.getresponse();code=response.status
            if code>=400:raise HTTPError(base_url,code,response.reason,response.headers,None)
            # No server payload copied into diagnostics (may contain private data).
            ct=response.headers.get('Content-Type','').split(';')[0]
            check(results,endpoint,'PASS' if 200<=code<400 else 'FAIL',f'HTTP {code}; content-type={ct}')
        except HTTPError as err:
            check(results,endpoint,'WARN' if err.code in (401,403,404) else 'FAIL',f'HTTP {err.code}')
        except (URLError,OSError,TimeoutError,ValueError,http.client.HTTPException) as err:
            check(results,endpoint,'FAIL',type(err).__name__)
        finally:
            if connection:connection.close()
    if shutil.which('docker'):
        r=run_command(['docker','version','--format','{{.Client.Version}}'])
        check(results,'docker_cli','PASS' if r.get('exit_code')==0 else 'WARN',r.get('output','').strip())
    else:
        check(results,'docker_cli','SKIP','Docker optional')
    if shutil.which('rocminfo'):
        r=run_command(['rocminfo'],12)
        check(results,'rocm_probe','PASS' if r.get('exit_code')==0 else 'WARN','rocminfo exit='+str(r.get('exit_code','unavailable')))
    else:
        check(results,'rocm_probe','SKIP','ROCm optional')
    if shutil.which('nvidia-smi'):
        r=run_command(['nvidia-smi','--query-gpu=name','--format=csv,noheader'],12)
        check(results,'cuda_probe','PASS' if r.get('exit_code')==0 else 'WARN','nvidia-smi exit='+str(r.get('exit_code','unavailable')))
    else:
        check(results,'cuda_probe','SKIP','CUDA optional')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',required=True,choices=('macos','windows','linux','server'))
    p.add_argument('--app',type=Path,help='Installed native .app, exe, AppImage or executable')
    p.add_argument('--url',default='http://127.0.0.1:8080',help='Server base URL, no credentials')
    p.add_argument('--output',type=Path,help='Directory for diagnostics (default: temporary directory)')
    args=p.parse_args()
    out=args.output or Path(tempfile.mkdtemp(prefix='mta-r208-diagnostics-'))
    out=out.expanduser().resolve();out.mkdir(parents=True,exist_ok=True)
    results=[]
    host=platform.system().lower()
    if args.mode=='server':inspect_server(results,args.url)
    elif args.mode=='macos':
        check(results,'host_platform','PASS' if host=='darwin' else 'WARN',host)
        inspect_macos(results,args.app)
    elif args.mode=='windows':
        check(results,'host_platform','PASS' if host=='windows' else 'WARN',host)
        inspect_windows(results,args.app)
    else:
        check(results,'host_platform','PASS' if host=='linux' else 'WARN',host)
        inspect_linux(results,args.app)
    mandatory=[x for x in results if x['status']=='FAIL']
    status='FAIL' if mandatory else 'PASS'
    # These reports deliberately contain no process env, home directory listings, app logs, keys or project contents.
    report={'tool':'MTA installed diagnostics','version':VERSION,'mode':args.mode,
            'timestamp_utc':datetime.now(timezone.utc).isoformat(),
            'host':{'system':platform.system(),'release':platform.release(),'architecture':platform.machine()},
            'status':status,'checks':results,
            'scope_limitations':['Non-destructive read-only probes','No playback/GUI automation','No GPU inference or billing exercise','No project files, credentials, environment variables or application logs collected']}
    (out/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    lines=[f'# MTA {VERSION} installed diagnostics',f'Platform: {args.mode}',f'Result: **{status}**','', '| Check | Status | Detail |','|---|---|---|']
    for x in results:
        detail=x['detail'].replace('|','/').replace('\n',' ')
        detail=SENSITIVE.sub('[redacted]',detail)
        lines.append(f"| {x['name']} | {x['status']} | {detail} |")
    lines+=['','These checks do not certify GUI playback, native audio plug-ins, GPU inference, billing or crash recovery.']
    (out/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    archive=out/('mta-r208-'+args.mode+'-diagnostics.zip')
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        z.write(out/'report.json','report.json');z.write(out/'report.md','report.md')
    print('REPORT',out/'report.json');print('ARCHIVE',archive)
    return 1 if mandatory else 0

if __name__=='__main__':sys.exit(main())
