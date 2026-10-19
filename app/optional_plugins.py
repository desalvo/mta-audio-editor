"""Opt-in, pinned-source VST3 catalog and installation outside project workspaces.

Catalog entries are code-reviewed, never provided by an HTTP caller. Source and
transitive notices remain alongside the build for local use/repackaging review.
"""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid

from . import auth

CATALOG=Path(__file__).with_name('optional_plugins_catalog.json')
LICENSES=Path(__file__).with_name('optional_plugin_licenses')
_LOCK=threading.Lock()
_JOBS={}


def plugin_root():
    # This directory is not under /data/projects and is never part of a project.
    default=auth.data_root().parent/'mta-optional-vst3'
    return Path(os.getenv('MTA_OPTIONAL_VST3_DIR',str(default))).expanduser().resolve()


def catalog():
    data=json.loads(CATALOG.read_text(encoding='utf-8'))
    reviewed=dt.date.fromisoformat(data['reviewed_at'])
    data['review_due']=dt.datetime.now(dt.timezone.utc).date()>reviewed+dt.timedelta(days=data['review_interval_days'])
    for p in data['plugins']:
        license_path=LICENSES/p['license_file']
        if not license_path.resolve().is_relative_to(LICENSES.resolve()) or hashlib.sha256(license_path.read_bytes()).hexdigest()!=p['license_sha256']:raise ValueError('Plugin catalog license integrity error')
        p['installed']=(plugin_root()/p['id']/p['revision']/'installation.json').is_file()
        p['supported']=sys.platform in p['platforms']
        p['available']=bool(p['enabled'] and p['supported'] and not data['review_due'])
    data['plugins'].sort(key=lambda p:(p['category'],p['name']))
    return data


def select(ids):
    data=catalog();known={p['id']:p for p in data['plugins']}
    if not isinstance(ids,list) or not ids or len(ids)>len(known) or len(set(ids))!=len(ids) or any(not isinstance(x,str) or x not in known for x in ids):raise ValueError('Select valid catalog plugins')
    selected=[known[x] for x in ids]
    if any(not p['available'] for p in selected):raise ValueError('Plugin unavailable or license review overdue')
    return selected


def _run(command,cwd,log,notify,timeout=3600):
    notify('command',Path(command[0]).name)
    env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_ALLOW_PROTOCOL':'https'}
    with log.open('ab') as output,subprocess.Popen(command,cwd=cwd,stdout=output,stderr=subprocess.STDOUT,env=env) as process:
        started=time.monotonic()
        try:
            while True:
                try:code=process.wait(timeout=min(10,max(.01,timeout-(time.monotonic()-started))));break
                except subprocess.TimeoutExpired:
                    notify('building',f'{Path(command[0]).name} · {int(time.monotonic()-started)}s')
                    if time.monotonic()-started>=timeout:raise TimeoutError('Plugin build command timed out')
            if code:raise RuntimeError(f'{Path(command[0]).name} failed (exit {code}); inspect installation log / toolchain requirements')
        finally:
            if process.poll() is None:process.kill();process.wait()


def commands(spec,source):
    if spec['builder']=='dpf':
        return [['make','-C','dpf/dgl','-j2','USE_FILE_BROWSER=false']]+[['make','-C',target,'-j2','vst3','USE_FILE_BROWSER=false'] for target in spec['targets']]
    folder=source/spec.get('source_subdir','.')
    build=source/'mta-build'
    configure=['cmake','-S',str(folder),'-B',str(build),'-DCMAKE_BUILD_TYPE=Release','-DCMAKE_POLICY_VERSION_MINIMUM=3.5','-DJUCE_COPY_PLUGIN_AFTER_BUILD=OFF','-DBUILD_TESTING=OFF','-DCHOWTAPE_BUILD_CLAP=OFF']
    return [configure,['cmake','--build',str(build),'--config','Release','--parallel','2','--target',*spec['targets']]]


def install_one(spec,notify=lambda *_:None):
    # A per-plugin immutable source revision, with recursive submodule gitlinks.
    work=auth.data_root()/'optional-plugin-builds'/spec['id']/spec['revision']
    source=work/'source';work.mkdir(parents=True,exist_ok=True);log=work/'install.log'
    if not source.exists():
        source.mkdir()
        _run(['git','init'],source,log,notify,60)
        _run(['git','remote','add','origin','https://github.com/'+spec['repo']+'.git'],source,log,notify,60)
    # Fetch the reviewed commit, never a moving branch. HTTPS only.
    notify('download',spec['name'])
    _run(['git','fetch','--depth','1','origin',spec['revision']],source,log,notify,600)
    _run(['git','checkout','--detach',spec['revision']],source,log,notify,60)
    _run(['git','submodule','update','--init','--recursive','--depth','1'],source,log,notify,1200)
    actual=subprocess.run(['git','rev-parse','HEAD'],cwd=source,capture_output=True,text=True,check=True,timeout=30).stdout.strip()
    if actual!=spec['revision']:raise ValueError('Plugin source revision mismatch')
    if hashlib.sha256((source/'LICENSE').read_bytes()).hexdigest()!=spec['license_sha256']:raise ValueError('Upstream plugin license changed; installation refused')
    notify('compile',spec['name'])
    for command in commands(spec,source):_run(command,source,log,notify)
    candidates=[p for p in source.rglob('*.vst3') if p.is_dir() and '.git' not in p.parts and any(c.is_file() and c.suffix.lower() in ('.so','.dll','') for c in p.rglob('*'))]
    if not candidates:raise ValueError('Build produced no VST3 bundles')
    # Deduplicate build/copy locations by bundle name; VST3 only (no VST2 SDK).
    bundles={p.name:p for p in candidates}
    destination=plugin_root()/spec['id']/spec['revision']
    destination.parent.mkdir(parents=True,exist_ok=True,mode=0o755)
    if destination.exists():return {'id':spec['id'],'revision':spec['revision'],'bundles':sorted(bundles)}
    notify('install',spec['name'])
    # Stage outside discovery root so a scan cannot observe a partial bundle.
    with tempfile.TemporaryDirectory(prefix='mta-vst3-stage-',dir=destination.parent.parent.parent) as staging:
        staged=Path(staging)/'content';staged.mkdir()
        for name,bundle in bundles.items():shutil.copytree(bundle,staged/name,symlinks=False)
        shutil.copy2(source/'LICENSE',staged/'LICENSE.txt')
        manifest={**spec,'bundles':sorted(bundles),'source_directory':str(source),'installed_at':int(time.time())}
        (staged/'installation.json').write_text(json.dumps(manifest,indent=2)+'\n')
        for file in staged.rglob('*'):file.chmod(0o755 if file.is_dir() or os.access(file,os.X_OK) else 0o644)
        os.replace(staged,destination)
    return {'id':spec['id'],'revision':spec['revision'],'bundles':sorted(bundles)}


def install(ids,notify=lambda *_:None):
    selected=select(ids)
    results=[]
    for n,spec in enumerate(selected):
        notify('plugin',f'{n+1}/{len(selected)} · {spec["name"]}')
        try:results.append(install_one(spec,notify))
        except (OSError,ValueError,RuntimeError,subprocess.SubprocessError,TimeoutError) as exc:results.append({'id':spec['id'],'error':str(exc)[:500]})
    return results


def start(ids):
    select(ids)
    if not _LOCK.acquire(blocking=False):raise ValueError('A plugin installation is already running')
    identifier=uuid.uuid4().hex
    job={'id':identifier,'state':'running','stage':'starting','message':'','started_at':time.time(),'results':[]};_JOBS[identifier]=job
    def execute():
        try:
            def update(stage,message):job.update(stage=stage,message=message)
            job['results']=install(ids,update)
            job['state']='completed_with_errors' if any('error' in x for x in job['results']) else 'completed'
        except Exception as exc:job.update(state='failed',message=type(exc).__name__)
        finally:job['finished_at']=time.time();_LOCK.release()
    threading.Thread(target=execute,daemon=True,name='mta-optional-vst3').start()
    return dict(job)


def status(identifier):
    if identifier not in _JOBS:raise ValueError('Plugin installation not found (server may have restarted)')
    return dict(_JOBS[identifier])


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description='Install optional reviewed VST3 plugins from pinned source')
    parser.add_argument('--list',action='store_true')
    parser.add_argument('--plugins',default='')
    parser.add_argument('--accept-licenses',action='store_true')
    args=parser.parse_args()
    if args.list:print(json.dumps(catalog(),indent=2))
    else:
        if not args.plugins or not args.accept_licenses:parser.error('--plugins and --accept-licenses required')
        chosen=[p['id'] for p in catalog()['plugins'] if p['available']] if args.plugins=='all' else args.plugins.split(',')
        result=install(chosen,lambda stage,message:print(stage+': '+message,flush=True))
        print(json.dumps(result,indent=2))
        if any('error' in x for x in result):raise SystemExit(1)
