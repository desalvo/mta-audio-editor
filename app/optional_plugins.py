"""Opt-in, pinned-source VST3 catalog and installation outside project workspaces.

Catalog entries are code-reviewed, never provided by an HTTP caller. Source and
transitive notices remain alongside the build for local use/repackaging review.
"""
from .service_admission import admitted
from .service_admission import worker_thread
import copy
import datetime as dt
import hashlib
import json
import os
import re
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
    from .runtime_paths import optional_vst3_root
    return optional_vst3_root(auth.data_root())


def catalog():
    data=json.loads(CATALOG.read_text(encoding='utf-8'))
    reviewed=dt.date.fromisoformat(data['reviewed_at'])
    data['review_due']=dt.datetime.now(dt.timezone.utc).date()>reviewed+dt.timedelta(days=data['review_interval_days'])
    for p in data['plugins']:
        license_path=LICENSES/p['license_file']
        if not license_path.resolve().is_relative_to(LICENSES.resolve()) or hashlib.sha256(license_path.read_bytes()).hexdigest()!=p['license_sha256']:raise ValueError('Plugin catalog license integrity error')
        p['installed']=(plugin_root()/p['id']/p['revision']/'installation.json').is_file()
        state_file=auth.data_root()/'optional-plugin-builds'/p['id']/p['revision']/'status.json'
        try:previous=json.loads(state_file.read_text())
        except (OSError,ValueError):previous={}
        p['state']='installed' if p['installed'] else ('failed' if previous.get('error') else 'not_installed')
        p['error']=previous.get('error','')
        p['supported']=sys.platform in p['platforms']
        p['available']=bool(p['enabled'] and p['supported'] and not data['review_due'])
    data['active_job']=next((j['id'] for j in list(_JOBS.values()) if j['state']=='running'),None)
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


@admitted('optional-plugin-install')
def install(ids,notify=lambda *_:None,on_result=lambda *_:None):
    selected=select(ids)
    results=[]
    for spec in selected:
        notify('plugin',spec['id'])
        try:result=install_one(spec,notify)
        except (OSError,ValueError,RuntimeError,subprocess.SubprocessError,TimeoutError) as exc:result={'id':spec['id'],'error':str(exc)[:500]}
        results.append(result)
        work=auth.data_root()/'optional-plugin-builds'/spec['id']/spec['revision'];work.mkdir(parents=True,exist_ok=True)
        temporary=work/'status.tmp';temporary.write_text(json.dumps(result));os.replace(temporary,work/'status.json')
        on_result(result)
    return results


@admitted('optional-plugins')
def start(ids):
    select(ids)
    if not _LOCK.acquire(blocking=False):raise ValueError('A plugin installation is already running')
    identifier=uuid.uuid4().hex
    job={'id':identifier,'state':'running','stage':'starting','message':'','started_at':time.time(),'results':[],'current_plugin':None,'plugins':{p:{'state':'queued','stage':'starting','message':''} for p in ids}};_JOBS[identifier]=job
    def execute():
        try:
            def update(stage,message):
                if stage=='plugin':job['current_plugin']=message
                job.update(stage=stage,message=message)
                current=job['current_plugin']
                if current:job['plugins'][current].update(state='installing',stage=stage,message=message)
            def complete(result):
                job['plugins'][result['id']].update(state='failed' if 'error' in result else 'installed',error=result.get('error',''))
                job['results'].append(result)
            install(ids,update,complete)
            job['state']='completed_with_errors' if any('error' in x for x in job['results']) else 'completed'
        except Exception as exc:
            job.update(state='failed',message=type(exc).__name__)
            for state in job['plugins'].values():
                if state['state'] in ('queued','installing'):state.update(state='failed',error=type(exc).__name__)
        finally:job['finished_at']=time.time();_LOCK.release()
    worker_thread(target=execute,daemon=True,name='mta-optional-vst3').start()
    return copy.deepcopy(job)


def status(identifier):
    if identifier not in _JOBS:raise ValueError('Plugin installation not found (server may have restarted)')
    return copy.deepcopy(_JOBS[identifier])


def _managed_package(identifier):
    if not isinstance(identifier,str) or not re.fullmatch(r'[a-z0-9-]+',identifier):raise ValueError('Invalid catalog plugin')
    spec=next((p for p in catalog()['plugins'] if p['id']==identifier),None)
    if spec is None:raise ValueError('Unknown catalog plugin')
    root=plugin_root().resolve();target=plugin_root()/identifier
    if target.is_symlink() or target.resolve().parent!=root:raise ValueError('Unsafe managed plugin path')
    return spec,target


def _uses(project,target):
    routes=[project.master_inserts]+[t.inserts for t in project.tracks]+[[t.instrument] for t in project.tracks if t.instrument]
    return any(i.plugin=='vst3' and Path(str(i.params.get('path',''))).resolve().is_relative_to(target.resolve()) for items in routes for i in items)


def uninstall_info(identifier):
    from .vst3_live import SESSIONS,SESSION_LOCK
    from . import vst3_editor
    from .storage import list_projects
    spec,target=_managed_package(identifier)
    with SESSION_LOCK,vst3_editor._LOCK:
        busy=any(not s.closed and _uses(s.project,target) for s in list(SESSIONS)) or any(proc.poll() is None for proc,_,_ in vst3_editor._JOBS.values())
    projects=[{'id':p.id,'title':p.title} for p in list_projects(is_admin=True) if _uses(p,target)]
    return {'id':identifier,'name':spec['name'],'installed':target.is_dir(),'in_use':busy,'projects':projects}


def uninstall(identifier,*,remove_build_cache=False):
    # Only allowlisted packages inside MTA's managed root can be removed.
    # The same process lock prevents a live host from starting while detaching.
    from .vst3_live import SESSIONS,SESSION_LOCK
    from . import vst3_editor
    if not _LOCK.acquire(blocking=False):raise ValueError('Wait for the current plugin installation to finish')
    detached=None
    try:
        spec,target=_managed_package(identifier)
        work=auth.data_root()/'optional-plugin-builds'/identifier
        if work.parent.is_symlink() or work.is_symlink() or work.resolve().parent!=(auth.data_root()/'optional-plugin-builds').resolve():raise ValueError('Unsafe plugin build cache path')
        with SESSION_LOCK,vst3_editor._LOCK:
            if any(proc.poll() is None for proc,_,_ in vst3_editor._JOBS.values()):raise ValueError('Close the desktop plugin editor before uninstalling plugins')
            if any(not s.closed and _uses(s.project,target) for s in list(SESSIONS)):raise ValueError('Stop playback and close live plugin editors/monitoring before uninstalling this plugin')
            if target.exists():
                detached=target.parent/('.mta-vst3-remove-'+uuid.uuid4().hex)
                os.replace(target,detached)
        # rmtree does not follow directory symlinks; roots above are checked.
        if detached:shutil.rmtree(detached)
        if remove_build_cache and work.exists():shutil.rmtree(work)
        elif work.is_dir():
            for status_file in work.glob('*/status.json'):
                if status_file.parent.is_symlink() or status_file.is_symlink():continue
                status_file.write_text(json.dumps({'id':identifier,'uninstalled_at':int(time.time())})+'\n')
        return {'id':identifier,'state':'not_installed','build_cache_removed':remove_build_cache,'name':spec['name']}
    finally:_LOCK.release()


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
