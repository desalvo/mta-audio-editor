"""Calibrated continuous HIP kernel-interval metering, independent of diagnostics.

GPU seconds mean the union of device kernel intervals for this task. CPU API
durations, copies, wall time and slot estimates never contribute to this unit.
"""
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import secrets
import tempfile
import time

METHOD='gpu-kernel-union-v1'
REPORT='gpu-verified.json'
VERIFIED_KINDS=frozenset(('ace-step','whisper','demucs','sam-audio','singer-separation','markers'))


def root():return Path(os.getenv('MTA_GPU_BILLING_ROOT','/var/lib/mta/gpu-billing'))


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def implementation():return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _key():
    directory=root()
    if directory.is_symlink() or directory.stat().st_mode&0o022:raise ValueError('Unsafe GPU metering directory')
    path=directory/'key'
    if path.is_symlink() or path.stat().st_mode&0o077:raise ValueError('Unsafe GPU metering key')
    data=path.read_bytes()
    if len(data)!=32:raise ValueError('Invalid GPU metering key')
    return data


def seal(value):return {'payload':value,'signature':hmac.new(_key(),canonical(value),hashlib.sha256).hexdigest()}


def unseal(envelope):
    if not isinstance(envelope,dict) or set(envelope)!={'payload','signature'}:raise ValueError('Invalid GPU envelope')
    expected=hmac.new(_key(),canonical(envelope['payload']),hashlib.sha256).hexdigest()
    if not isinstance(envelope['signature'],str) or not hmac.compare_digest(expected,envelope['signature']):raise ValueError('Invalid GPU signature')
    return envelope['payload']


def policy():
    path=root()/'policy.json'
    if path.is_symlink() or path.stat().st_size>16384:raise ValueError('Unsafe GPU policy')
    value=unseal(json.loads(path.read_text()))
    if (value.get('method')!=METHOD or value.get('implementation')!=implementation()
            or value.get('expires_at',0)<=time.time() or value.get('enabled') is not True):
        raise ValueError('GPU calibration absent, expired or invalidated by implementation update')
    return value


def readiness():
    try:
        value=policy()
        return {'ready':True,'method':METHOD,'calibration_id':value['id'],'expires_at':value['expires_at'],
                'unit':'per-task union of GPU kernel execution intervals in seconds'}
    except (OSError,ValueError,TypeError,KeyError):return {'ready':False,'method':METHOD,'reason':'calibration-required'}


def fingerprint(torch):
    device=torch.cuda.get_device_properties(torch.cuda.current_device())
    return {'torch':str(torch.__version__),'hip':str(torch.version.hip),'cuda':str(getattr(torch.version,'cuda','')),'device':str(device.name),
            'architecture':str(getattr(device,'gcnArchName','')),'uuid':str(getattr(device,'uuid','')),
            'kernel':os.uname().release,'host':os.uname().nodename}


def intervals(trace,wall):
    try:from .ace_gpu_profiler import kernel_activity
    except ImportError:from ace_gpu_profiler import kernel_activity
    if not isinstance(trace,dict) or not isinstance(trace.get('traceEvents'),list):raise ValueError('Invalid trace')
    for key in ('dropped_events','droppedEvents','errors','warnings'):
        if trace.get(key):raise ValueError('Incomplete trace')
    launches={};kernels=[];controls=[];events_by_id={};control_owner=None
    for event in trace['traceEvents']:
        if isinstance(event,dict) and event.get('ph')=='X' and event.get('name') in ('MTA_GPU_CONTROL_BEFORE','MTA_GPU_CONTROL_AFTER'):
            ts,dur=event.get('ts'),event.get('dur')
            if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0 for v in (ts,dur)):
                raise ValueError('Invalid GPU control interval')
            controls.append((event['name'],ts,ts+dur))
            if not dur:raise ValueError('Empty GPU control')
            owner=(event.get('pid'),event.get('tid'))
            if None in owner:raise ValueError('GPU control owner missing')
            if control_owner is not None and owner!=control_owner:raise ValueError('Mixed control owners')
            control_owner=owner
    if len(controls)!=2 or {c[0] for c in controls}!={'MTA_GPU_CONTROL_BEFORE','MTA_GPU_CONTROL_AFTER'}:
        raise ValueError('GPU capture health controls missing')
    before=next(c for c in controls if c[0]=='MTA_GPU_CONTROL_BEFORE')
    after=next(c for c in controls if c[0]=='MTA_GPU_CONTROL_AFTER')
    if before[2]>=after[1]:raise ValueError('Unordered GPU controls')
    control_ids={name:set() for name,_,_ in controls}
    for event in trace['traceEvents']:
        if not isinstance(event,dict):raise ValueError('Invalid event')
        name=str(event.get('name',''))
        if 'GraphLaunch' in name:raise ValueError('Graph coverage is not calibrated')
        args=event.get('args') or {}
        if not isinstance(args,dict):raise ValueError('Invalid event identity')
        correlation=args.get('correlation')
        if event.get('ph')=='X' and event.get('cat') in ('kernel','gpu_kernel'):
            kernels.append(correlation);events_by_id[correlation]=event
        elif event.get('ph')=='X' and any(name.startswith(n) for n in
             ('hipLaunchKernel','hipExtModuleLaunchKernel','hipModuleLaunchKernel','cudaLaunchKernel','cuLaunchKernel')):
            if type(correlation) is not int or correlation in launches:raise ValueError('Ambiguous dispatch')
            ts=event.get('ts');duration=event.get('dur')
            if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or x<0 for x in (ts,duration)):
                raise ValueError('Invalid dispatch time')
            if (event.get('pid'),event.get('tid'))!=control_owner or not before[1]<=ts<=after[2]:
                raise ValueError('Unattributed GPU dispatch')
            launches[correlation]=True
            for label,start,end in controls:
                if start<=event.get('ts',-1)<=end:control_ids[label].add(correlation)
    if not kernels or any(type(v) is not int for v in kernels) or len(set(kernels))!=len(kernels) or set(kernels)!=set(launches):
        raise ValueError('GPU launch/kernel coverage mismatch')
    if any(not ids or any(identity not in events_by_id for identity in ids) for ids in control_ids.values()):
        raise ValueError('GPU capture control dispatch missing')
    if any(events_by_id[i].get('dur',0)<=0 for ids in control_ids.values() for i in ids):raise ValueError('Invalid GPU control kernel')
    kernel_activity(trace,wall)  # Validate control and task timestamps before filtering.
    if any(e['ts']<before[1] or e['ts']+e['dur']>after[2] for e in events_by_id.values()):raise ValueError('GPU kernel outside capture controls')
    excluded=set().union(*control_ids.values())
    filtered={'traceEvents':[e for identity,e in events_by_id.items() if identity not in excluded]}
    return kernel_activity(filtered,wall)


def capture(torch,call):
    if not torch.cuda.is_available():raise ValueError('CUDA/ROCm device required')
    activities=[torch.profiler.ProfilerActivity.CPU,torch.profiler.ProfilerActivity.CUDA]
    if not set(activities)<=torch.profiler.supported_activities():raise ValueError('GPU tracing unavailable')
    torch.cuda.synchronize()
    probe=torch.empty(32,device='cuda')
    started=time.monotonic();success=False
    with torch.profiler.profile(activities=activities,record_shapes=False,with_stack=False,profile_memory=False) as profile:
        try:
            with torch.profiler.record_function('MTA_GPU_CONTROL_BEFORE'):
                probe.fill_(1);torch.cuda.synchronize()
            result=call();torch.cuda.synchronize()
            with torch.profiler.record_function('MTA_GPU_CONTROL_AFTER'):
                probe.fill_(2);torch.cuda.synchronize()
            success=True
        finally:
            torch.cuda.synchronize()
    if not success:raise ValueError('Incomplete capture')
    wall=time.monotonic()-started
    with tempfile.TemporaryDirectory(prefix='mta-gpu-verified-') as folder:
        path=Path(folder)/'trace.json';profile.export_chrome_trace(str(path))
        if path.stat().st_size>64*1024*1024:raise ValueError('GPU trace exceeds verified limit')
        raw=path.read_bytes();trace=json.loads(raw)
    seconds,count,device=intervals(trace,wall)
    return result,{'gpu_seconds':seconds,'kernel_count':count,'device_id':device,'wall_seconds':wall,
        'trace_sha256':hashlib.sha256(raw).hexdigest(),'fingerprint':fingerprint(torch),'capture_start':started,'capture_end':time.monotonic()}


def measured(task,call,*,publish):
    """No retry of inference if profiling or evidence validation fails."""
    try:
        import torch
    except ImportError:return call()
    try:
        certificate=policy()
        if fingerprint(torch)!=certificate['fingerprint']:return call()
    except (OSError,ValueError,TypeError,KeyError):return call()
    called=False;output=None;failure=None
    def once():
        nonlocal called,output,failure
        called=True
        try:output=call();return output
        except BaseException as exc:failure=exc;raise
    try:
        output,record=capture(torch,once)
        evidence=seal({**record,'id':secrets.token_hex(16),'task_id':task,'method':METHOD,
          'implementation':implementation(),'calibration_id':certificate['id'],'complete':True,
          'recorded_at':time.time()})
        publish(evidence)
    except Exception:
        if failure is not None:raise failure
        if not called:return call()
        # A successful inference remains deliverable, with no GPU charge.
    return output


def persist(job_id,envelope,expected_task):
    from .auth import db
    value=unseal(envelope);certificate=policy()
    validate_record(value)
    seconds=value.get('gpu_seconds');wall=value.get('wall_seconds')
    if (value.get('task_id')!=expected_task or value.get('method')!=METHOD or value.get('complete') is not True
            or value.get('implementation')!=implementation() or value.get('calibration_id')!=certificate['id']
            or value.get('fingerprint')!=certificate['fingerprint']
            or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0 for v in (seconds,wall))
            or wall<=0 or seconds>wall*1.1+.05 or type(value.get('kernel_count')) is not int or value['kernel_count']<0
            or abs(time.time()-value.get('recorded_at',0))>3600):raise ValueError('Invalid GPU task evidence')
    with db() as con:
        con.execute('BEGIN IMMEDIATE')
        from .worker_loss_resolution import note_evidence_in_transaction
        note_evidence_in_transaction(con,job_id)
        con.execute('''CREATE TABLE IF NOT EXISTS ai_verified_gpu_evidence
          (job_id TEXT PRIMARY KEY,evidence_id TEXT UNIQUE NOT NULL,seconds REAL NOT NULL,envelope TEXT NOT NULL)''')
        existing=con.execute('SELECT envelope FROM ai_verified_gpu_evidence WHERE job_id=?',(job_id,)).fetchone()
        encoded=canonical(envelope).decode()
        if existing:
            if existing[0]!=encoded:raise ValueError('Conflicting GPU evidence')
        else:con.execute('INSERT INTO ai_verified_gpu_evidence VALUES(?,?,?,?)',(job_id,value['id'],seconds,encoded))
    return seconds


def append_report(folder,envelope,task):
    value=unseal(envelope)
    if value.get('task_id')!=task:raise ValueError('GPU task binding mismatch')
    path=Path(folder)/REPORT
    if path.is_symlink():raise ValueError('Unsafe GPU evidence path')
    previous=json.loads(path.read_text()) if path.exists() else []
    if not isinstance(previous,list) or len(previous)>64:raise ValueError('Too many GPU evidence segments')
    if any(item.get('signature')==envelope['signature'] for item in previous):return
    atomic_json(path,previous+[envelope])


def consume_report(job_id,folder,*,ace=False,expected_segments=None):
    from .ai_worker_artifacts import _read_private_file
    from .auth import db
    envelopes=json.loads(_read_private_file(Path(folder)/REPORT,128*1024))
    if not isinstance(envelopes,list) or not 1<=len(envelopes)<=64:raise ValueError('Incomplete GPU evidence set')
    if expected_segments is not None and len(envelopes)!=expected_segments:raise ValueError('Incomplete GPU segment coverage')
    values=[unseal(e) for e in envelopes]
    tasks={v['task_id'] for v in values}
    if (not ace and tasks!={job_id}) or (ace and len(tasks)!=1):raise ValueError('GPU task mismatch')
    ordered=sorted(values,key=lambda value:value['capture_start'])
    if any(a['capture_end']>b['capture_start'] for a,b in zip(ordered,ordered[1:])):raise ValueError('Overlapping GPU capture segments')
    ids=[v['id'] for v in values]
    if len(set(ids))!=len(ids):raise ValueError('Duplicate GPU evidence')
    first=values[0]
    for value,envelope in zip(values,envelopes):
        validate_record(value)
        if value['fingerprint']!=first['fingerprint'] or value['calibration_id']!=first['calibration_id']:
            raise ValueError('Mixed GPU runtime evidence')
        # Validate every constituent using the same rules, without committing.
        certificate=policy()
        if (value.get('complete') is not True or value.get('method')!=METHOD
                or value.get('implementation')!=implementation() or value['calibration_id']!=certificate['id']
                or value['fingerprint']!=certificate['fingerprint']
                or any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or x<0 for x in (value.get('gpu_seconds'),value.get('wall_seconds')))
                or value['wall_seconds']<=0 or value['gpu_seconds']>value['wall_seconds']*1.1+.05
                or value['capture_end']<=value['capture_start']):raise ValueError('Uncalibrated evidence')
    combined={**first,'task_id':job_id,'id':hashlib.sha256(canonical(sorted(ids))).hexdigest(),
      'gpu_seconds':sum(v['gpu_seconds'] for v in values),'wall_seconds':sum(v['wall_seconds'] for v in values),
      'kernel_count':sum(v['kernel_count'] for v in values),'trace_sha256':hashlib.sha256(canonical(ids)).hexdigest()}
    # Reserve all constituent IDs first; a differently grouped replay also fails.
    with db() as con:
        con.execute('CREATE TABLE IF NOT EXISTS ai_gpu_evidence_claims(id TEXT PRIMARY KEY,job_id TEXT NOT NULL)')
        con.execute('BEGIN IMMEDIATE')
        from .worker_loss_resolution import note_evidence_in_transaction
        note_evidence_in_transaction(con,job_id)
        for identity in ids:
            row=con.execute('SELECT job_id FROM ai_gpu_evidence_claims WHERE id=?',(identity,)).fetchone()
            if row and row[0]!=job_id:raise ValueError('GPU evidence already consumed')
            con.execute('INSERT OR IGNORE INTO ai_gpu_evidence_claims VALUES(?,?)',(identity,job_id))
    return persist(job_id,seal(combined),job_id)


def validate_record(value):
    import re
    for key in ('id','task_id','calibration_id'):
        if not isinstance(value.get(key),str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',value[key]):raise ValueError('Invalid evidence identity')
    if not isinstance(value.get('trace_sha256'),str) or not re.fullmatch(r'[a-f0-9]{64}',value['trace_sha256']):raise ValueError('Invalid trace digest')
    for key in ('recorded_at','capture_start','capture_end','gpu_seconds','wall_seconds'):
        number=value.get(key)
        if isinstance(number,bool) or not isinstance(number,(int,float)) or not math.isfinite(number) or number<0:raise ValueError('Invalid evidence interval')
    if abs(time.time()-value['recorded_at'])>3600 or value['capture_start']>=value['capture_end']:raise ValueError('Stale GPU evidence')
    if type(value.get('kernel_count')) is not int or value['kernel_count']<0 or ((value['gpu_seconds']>0)!=(value['kernel_count']>0)):raise ValueError('Invalid GPU kernel count')
    if type(value.get('device_id')) is not int or value['device_id']<0:raise ValueError('Invalid GPU device')


def require_evidence(job_id,usage):
    from .auth import db
    with db() as con:
        exists=con.execute("SELECT 1 FROM sqlite_master WHERE name='ai_verified_gpu_evidence'").fetchone()
        row=con.execute('SELECT seconds FROM ai_verified_gpu_evidence WHERE job_id=?',(job_id,)).fetchone() if exists else None
    if not row or usage.get('gpu_seconds')!=row[0] or 'gpu_energy_joules' in usage:
        raise ValueError('GPU billing requires persisted task evidence')


def calibrate(torch):
    root().mkdir(parents=True,exist_ok=True,mode=0o700)
    key=root()/'key'
    if not key.exists():
        fd=os.open(key,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as stream:stream.write(secrets.token_bytes(32))
    # Warmup, empty/CPU-only negative control and repeated known GPU dispatches.
    a=torch.randn(1024,1024,device='cuda');b=torch.randn_like(a)
    torch.mm(a,b);torch.cuda.synchronize()
    _,negative=capture(torch,lambda:None)
    if negative['gpu_seconds']!=0 or negative['kernel_count']!=0:raise ValueError('Negative control produced GPU activity')
    samples=[]
    for _ in range(3):
        _,sample=capture(torch,lambda:[torch.mm(a,b) for _ in range(8)])
        if sample['kernel_count']<8:raise ValueError('Calibration missed GPU work')
        samples.append(sample)
    value={'id':secrets.token_hex(16),'enabled':True,'method':METHOD,'implementation':implementation(),
      'fingerprint':fingerprint(torch),'expires_at':time.time()+30*86400,'samples':samples}
    atomic_json(root()/'policy.json',seal(value))
    return readiness()


def atomic_json(path,value):
    fd,name=tempfile.mkstemp(dir=path.parent,prefix='.gpu-billing-')
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,'wb') as stream:
            stream.write(canonical(value));stream.flush();os.fsync(stream.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)
