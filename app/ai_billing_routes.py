"""Administrator-only metering, tariff and period-closing endpoints."""
from __future__ import annotations
import os
import csv
import io
import secrets
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from .auth import require_admin
from . import ai_billing, ai_access

router=APIRouter()

def _error(call):
    try: return call()
    except (ValueError,TypeError,KeyError,OverflowError) as exc: raise HTTPException(400,str(exc)) from exc

@router.get('/api/admin/ai-billing/report')
def report(request:Request,period:str='month',user_id:int|None=None,anchor:str|None=None,start:str|None=None,end:str|None=None):
    require_admin(request)
    return _error(lambda:ai_billing.report(period,user_id=user_id,anchor=anchor,start=start,end=end))

@router.get('/api/admin/ai-billing/readiness')
def billing_readiness(request: Request):
    require_admin(request)
    from .ai_billing_readiness import check
    return check()

@router.get('/api/admin/ai-billing/reconcile')
def reconcile(request: Request, user_id: int, start: str, end: str):
    require_admin(request)
    return _error(lambda: ai_billing.reconcile_period(user_id, start, end))


@router.get('/api/admin/ai-billing/prices')
def prices(request:Request):
    require_admin(request)
    return {'currency':'EUR','prices_micro':ai_billing.prices(),'units':ai_billing.UNITS,'validity':ai_billing.tariff_history()}

@router.put('/api/admin/ai-billing/prices/{resource}')
def update_price(resource:str,body:dict,request:Request):
    require_admin(request)
    return _error(lambda:(ai_billing.set_price(resource,body['micro_per_unit'],valid_from=body.get('valid_from'),valid_until=body.get('valid_until')),{'ok':True})[1])

@router.post('/api/admin/ai-billing/close')
def close(request:Request,body:dict):
    require_admin(request)
    return _error(lambda:ai_billing.close_period(int(body['user_id']),body['start'],body['end']))

@router.get('/api/admin/ai-billing/audit-closed')
def audit_closed(request: Request, user_id: int | None = None):
    require_admin(request)
    return _error(lambda: ai_billing.audit_closed_invoices(user_id))

@router.get('/api/admin/ai-billing/invoices')
def invoices(request:Request,user_id:int|None=None):
    require_admin(request)
    return {'items':ai_billing.bills(user_id)}

@router.put('/api/admin/ai-billing/schedules/{user_id}')
def schedule(request:Request,user_id:int,body:dict):
    require_admin(request)
    return _error(lambda:(ai_billing.configure_schedule(user_id,body['cadence'],body.get('enabled',True)),{'ok':True})[1])

@router.get('/api/admin/ai-billing/schedules')
def schedule_list(request:Request):
    require_admin(request)
    return {'items':ai_billing.schedules()}

@router.post('/api/admin/ai-billing/run-schedules')
def process_schedules(request:Request):
    require_admin(request)
    return {'items':ai_billing.run_scheduled_closures()}

@router.get('/api/admin/ai-billing/export.csv')
def export_csv(request:Request,period:str='month',user_id:int|None=None,anchor:str|None=None,start:str|None=None,end:str|None=None):
    require_admin(request)
    data=_error(lambda:ai_billing.report(period,user_id=user_id,anchor=anchor,start=start,end=end))
    buf=io.StringIO()
    writer=csv.writer(buf)
    writer.writerow(['utc_date','user_id','jobs','metered_jobs','cost_micro_eur','resources_json'])
    for r in data['rows']:
        writer.writerow([r['day'],r['user_id'],r['jobs'],r['metered_jobs'],r['cost_micro'],
                         __import__('json').dumps(r['resources'],sort_keys=True)])
    return Response(buf.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="ai-usage.csv"'})

@router.get('/api/admin/ai-billing/gpu-calibrations')
def list_gpu_calibrations(request: Request):
    require_admin(request)
    from .ai_gpu_energy_estimator import calibrations
    return {'items': calibrations()}


@router.put('/api/admin/ai-billing/gpu-calibrations')
def save_gpu_calibration(request: Request, body: dict):
    require_admin(request)
    from .ai_gpu_energy_estimator import EnergyCalibration, store_calibration
    def save():
        profile = EnergyCalibration(gpu_id=body['gpu_id'],
                                    idle_watts=float(body['idle_watts']),
                                    full_load_watts=float(body['full_load_watts']))
        store_calibration(profile)
        return {'ok': True, 'billing_status': 'calibration_only_not_certified'}
    return _error(save)


@router.post('/api/admin/ai-billing/gpu-energy-estimate')
def admin_gpu_energy_estimate(request: Request, body: dict):
    require_admin(request)
    from .ai_gpu_energy_estimator import EnergyCalibration, calibrations, estimate_job_energy
    def calculate():
        p = next((row for row in calibrations() if row['gpu_id'] == body['gpu_id']), None)
        if p is None:
            raise ValueError('GPU calibration not found')
        return estimate_job_energy(EnergyCalibration(p['gpu_id'],p['idle_watts'],p['full_load_watts']),
            gpu_engine_seconds=float(body['gpu_engine_seconds']),
            job_wall_seconds=float(body['job_wall_seconds']),
            exclusive_gpu=body.get('exclusive_gpu') is True,
            complete_lifecycle=body.get('complete_lifecycle') is True,
            baseline_policy=body.get('baseline_policy','incremental'))
    return _error(calculate)


@router.post('/api/ai-jobs')
def start_remote_job(request:Request,body:dict):
    header=request.headers.get('authorization','')
    token=header[7:] if header.lower().startswith('bearer ') else ''
    identity=ai_access.authenticate(token)
    if not identity:
        raise HTTPException(401,'Valid AI user token required')
    # The backend worker must independently claim/execute the job. Creating a
    # ledger entry does not itself schedule arbitrary commands on the host.
    return _error(lambda:{'job_id':ai_billing.create_job(identity['user_id'],body['kind'],identity['id']),
                          'status':'running','execution':'worker-required'})

@router.post('/api/internal/ai-metering/jobs/{job_id}/finish')
def submit_metering(job_id:str,request:Request,body:dict):
    # Strictly opt-in; must not be exposed through ingress. A service-specific key
    # is not an end-user token; avoid forwarding it to ACE-Step.
    expected=os.getenv('MTA_AI_METERING_KEY','')
    provided=request.headers.get('x-mta-metering-key','')
    if not expected or not secrets.compare_digest(provided,expected):
        raise HTTPException(403,'Metering agent authentication required')
    return _error(lambda:(ai_billing.finish_job(job_id,body['status'],body.get('usage'),source=body.get('source','worker')),{'ok':True})[1])

@router.get('/admin/ai-billing',response_class=HTMLResponse)
def billing_page(request:Request):
    require_admin(request)
    return HTMLResponse('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MTA AI accounting</title>
<style>body{font:15px system-ui;max-width:1200px;margin:auto;padding:22px;color:#222}input,select,button{padding:8px;margin:5px}table{border-collapse:collapse;width:100%}th,td{text-align:left;border-bottom:1px solid #ddd;padding:7px}canvas{width:100%;height:220px;border:1px solid #ddd;border-radius:8px}section{margin:20px 0}small{color:#555}</style>
<h1>AI resource accounting and billing</h1><p><a href="/admin/ai-tokens">Access tokens</a></p>
<section><label>Period <select id="period"><option value="day">Daily</option><option value="week">Weekly</option><option selected value="month">Monthly</option><option value="year">Yearly</option><option value="custom">Custom</option></select></label><label>Anchor date <input id="anchor" type="date"></label><label>From <input id="start" type="date"></label><label>Through <input id="end" type="date"></label><label>User ID (blank=all) <input id="uid" type="number" min="1"></label><button id="load">Refresh</button><button id="csv">Export CSV</button></section>
<section><h2>Summary</h2><p id="totals"></p><canvas id="chart" width="980" height="230" role="img" aria-label="Daily estimated charges"></canvas><table><thead><tr><th>Date</th><th>User</th><th>Jobs</th><th>Metered jobs</th><th>Estimated EUR</th><th>Resource units</th></tr></thead><tbody id="rows"></tbody></table></section>
<section><h2>Billing readiness</h2><button id="readiness-refresh">Check readiness</button><pre id="readiness"></pre></section>
<section><h2>Resource prices</h2><small>Rates in EUR per resource unit. Specify UTC validity dates (end exclusive); leave end blank for a currently effective tariff. Billing periods are immutable snapshots.</small><table><thead><tr><th>Resource</th><th>Price EUR/unit</th><th>Valid from (UTC)</th><th>Valid until (optional)</th><th>Action</th></tr></thead><tbody id="rates"></tbody></table></section>
<section><h2>Automatic UTC billing</h2><label>User ID <input type="number" id="autouser" min="1"></label><label>Cadence <select id="autocadence"><option value="month">Monthly</option><option value="week">Weekly</option><option value="year">Yearly</option></select></label><button id="autosave">Save schedule</button><button id="autorun">Run due closures</button><pre id="sched"></pre></section>
<section><h2>Close billing period</h2><label>User ID <input id="billuser" type="number" min="1"></label><label>Start <input id="billstart" type="date"></label><label>Through <input id="billend" type="date"></label><button id="closebill">Close</button><p id="message" role="status"></p><h3>Closed periods</h3><pre id="bills"></pre></section>
<script>
const $=id=>document.getElementById(id);const eur=m=>(m/1e6).toFixed(6);
async function api(path,method='GET',body){let r=await fetch(path,{method,credentials:'same-origin',headers:{'Content-Type':'application/json','x-mta-request':'1'},body:body?JSON.stringify(body):undefined});let d=await r.json();if(!r.ok)throw Error(d.detail||r.status);return d}
async function load(){try{let p=new URLSearchParams({period:$('period').value});for(let k of ['anchor','start','end'])if($(k).value)p.set(k,$(k).value);if($('uid').value)p.set('user_id',$('uid').value);let d=await api('/api/admin/ai-billing/report?'+p);$('totals').textContent=`Jobs: ${d.job_count} · Unmetered: ${d.unmetered_jobs} · Total estimate: €${eur(d.total_micro)}`;let rows=$('rows');rows.replaceChildren();for(let r of d.rows){let tr=document.createElement('tr');for(let v of [r.day,r.user_id,r.jobs,r.metered_jobs,eur(r.cost_micro),JSON.stringify(r.resources)]){let td=document.createElement('td');td.textContent=v;tr.append(td)}rows.append(tr)}draw(d.rows);let v=await api('/api/admin/ai-billing/prices');$('rates').replaceChildren();for(let k of v.units){let tr=document.createElement('tr'),name=document.createElement('td'),td=document.createElement('td'),fromtd=document.createElement('td'),untiltd=document.createElement('td'),action=document.createElement('td'),input=document.createElement('input'),from=document.createElement('input'),until=document.createElement('input'),btn=document.createElement('button');name.textContent=k;input.type='number';input.step='0.000001';input.min='0';input.value=eur(v.prices_micro[k]||0);from.type='date';until.type='date';fromtd.append(from);untiltd.append(until);btn.textContent='Save';btn.onclick=async()=>{try{await api('/api/admin/ai-billing/prices/'+k,'PUT',{micro_per_unit:Math.round(Number(input.value)*1e6),valid_from:from.value||undefined,valid_until:until.value||undefined});$('message').textContent='Rate saved';}catch(e){$('message').textContent=e.message}};td.append(input);action.append(btn);tr.append(name,td,fromtd,untiltd,action);$('rates').append(tr)}$('bills').textContent=JSON.stringify((await api('/api/admin/ai-billing/invoices')).items,null,2)}catch(e){$('message').textContent=e.message}}
function draw(rows){let c=$('chart'),ctx=c.getContext('2d');ctx.clearRect(0,0,c.width,c.height);let grouped={};for(let r of rows)grouped[r.day]=(grouped[r.day]||0)+r.cost_micro;let vals=Object.entries(grouped).sort((a,b)=>a[0].localeCompare(b[0]));if(!vals.length){ctx.fillText('No jobs in period',30,60);return}let max=Math.max(1,...vals.map(x=>x[1])),w=(c.width-70)/vals.length;vals.forEach(([day,val],i)=>{let h=val/max*165;ctx.fillStyle='#326f9b';ctx.fillRect(45+i*w,185-h,Math.max(1,w-3),h);ctx.fillStyle='#222';ctx.font='11px sans-serif';ctx.fillText(day.slice(5),45+i*w,205,Math.max(10,w-3))});ctx.fillText('EUR',8,16)}
async function readiness(){try{$('readiness').textContent=JSON.stringify(await api('/api/admin/ai-billing/readiness'),null,2)}catch(e){$('readiness').textContent=e.message}}$('readiness-refresh').onclick=readiness;readiness();
$('csv').onclick=()=>{let p=new URLSearchParams({period:$('period').value});for(let k of ['anchor','start','end'])if($(k).value)p.set(k,$(k).value);if($('uid').value)p.set('user_id',$('uid').value);location.href='/api/admin/ai-billing/export.csv?'+p};$('autosave').onclick=async()=>{try{await api('/api/admin/ai-billing/schedules/'+Number($('autouser').value),'PUT',{cadence:$('autocadence').value});$('sched').textContent=JSON.stringify((await api('/api/admin/ai-billing/schedules')).items,null,2)}catch(e){$('message').textContent=e.message}};$('autorun').onclick=async()=>{try{$('sched').textContent=JSON.stringify((await api('/api/admin/ai-billing/run-schedules','POST')).items,null,2)}catch(e){$('message').textContent=e.message}};$('load').onclick=load;$('closebill').onclick=async()=>{if(!confirm('Close immutable billing period?'))return;try{let d=await api('/api/admin/ai-billing/close','POST',{user_id:Number($('billuser').value),start:$('billstart').value,end:$('billend').value});$('message').textContent='Period #'+d.id+' total €'+eur(d.total_micro);await load()}catch(e){$('message').textContent=e.message}};load();
</script></html>''')

@router.post('/api/ai-jobs/execute')
def execute_remote_ai_job(request: Request, body: dict):
    """Authenticated execution with fixed operator-configured worker and CPU metering.

    This endpoint only handles self-contained JSON plans. Audio input transport
    is not yet supported: do not expose arbitrary filesystem paths or commands.
    """
    header = request.headers.get('authorization', '')
    token = header[7:] if header.lower().startswith('bearer ') else ''
    identity = ai_access.authenticate(token)
    if not identity:
        raise HTTPException(401, 'Valid AI token required')
    from .ai_metering_agent import execute_registered_worker
    from .ai_worker_protocol import WorkerUnavailable
    kind = body.get('kind', '')
    plan = body.get('plan')
    if not isinstance(plan, dict):
        raise HTTPException(400, 'JSON worker plan required')
    # Local filesystem paths must never be provided by remote callers.
    if any(k in plan for k in ('source_audio', 'input_path', 'output_path', 'command', 'executable')):
        raise HTTPException(400, 'File-backed plans require staged authenticated transfer')
    from . import ai_request_dedup as dedup
    import json
    key = request.headers.get('x-mta-ai-idempotency-key', '')
    if key:
        try:
            dedup.admit(identity['user_id'], key, dedup.fingerprint(kind, json.dumps(plan, sort_keys=True).encode(), b''))
        except dedup.DuplicateAIRequest as exc:
            raise HTTPException(409, {'reason': 'duplicate_request', 'state': exc.state, 'job_id': exc.job_id}) from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
    try:
        result, meta = execute_registered_worker(identity['user_id'], kind, plan, token_id=identity['id'])
    except WorkerUnavailable as exc:
        if key: dedup.finalize(identity['user_id'], key, state='failed')
        raise HTTPException(503, str(exc)) from exc
    except (ValueError, TypeError) as exc:
        if key: dedup.finalize(identity['user_id'], key, state='failed')
        raise HTTPException(400, str(exc)) from exc
    finally:
        pass  # Unexpected crashes deliberately retain an admitted claim.
    if key:
        from .ai_result_cache import save as save_result
        # Best effort: metering is already finalized; inability to retain a
        # response must not cause the same job to be run or billed twice.
        try:
            save_result(identity['user_id'], key, result, meta.get('media_type', 'audio/wav'), meta['job_id'])
        except (OSError, ValueError):
            pass
        dedup.finalize(identity['user_id'], key, job_id=meta['job_id'])
    if len(result) > 32 * 1024 * 1024:
        raise HTTPException(413, 'AI result exceeds response limit')
    return Response(result, media_type=meta.get('media_type', 'audio/wav'), headers={'X-MTA-AI-Job-ID': meta['job_id']})


@router.get('/api/ai-jobs/request-status/{request_key}')
def remote_request_status(request_key: str, request: Request):
    """Safe status lookup for timed-out remote requests; never starts a job."""
    header = request.headers.get('authorization', '')
    token = header[7:] if header.lower().startswith('bearer ') else ''
    identity = ai_access.authenticate(token)
    if not identity:
        raise HTTPException(401, 'Valid AI token required')
    from .ai_request_dedup import request_status
    try:
        status = request_status(identity['user_id'], request_key)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if status is None:
        raise HTTPException(404, 'AI request not found')
    return status


@router.get('/api/ai-jobs/request-result/{request_key}')
def remote_request_result(request_key: str, request: Request):
    """Owner-only, read-only replay of a completed request, never inference."""
    header = request.headers.get('authorization', '')
    token = header[7:] if header.lower().startswith('bearer ') else ''
    identity = ai_access.authenticate(token)
    if not identity:
        raise HTTPException(401, 'Valid AI token required')
    from .ai_request_dedup import request_status
    from .ai_result_cache import load
    try:
        status = request_status(identity['user_id'], request_key)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if status is None:
        raise HTTPException(404, 'AI request not found')
    if status['state'] != 'completed' or not status['job_id']:
        raise HTTPException(409, 'AI request has no completed result')
    result = load(identity['user_id'], request_key, status['job_id'])
    if result is None:
        raise HTTPException(410, 'Result not retained or expired; inference will not be repeated')
    payload, media_type = result
    return Response(payload, media_type=media_type, headers={'X-MTA-AI-Job-ID': status['job_id'], 'Cache-Control':'private, no-store'})


@router.get('/api/ai-jobs/worker-capabilities')
def ai_worker_capabilities(request: Request):
    header = request.headers.get('authorization', '')
    token = header[7:] if header.lower().startswith('bearer ') else ''
    if not ai_access.authenticate(token):
        raise HTTPException(401, 'Valid AI token required')
    from .ai_worker_registry import available_workers
    return {'workers': available_workers(), 'audio_transport': 'wav', 'output': ['wav', 'artifact-zip-v1']}


@router.post('/api/ai-jobs/execute-audio/{kind}')
async def execute_remote_ai_audio_job(kind: str, request: Request):
    """WAV upload to a fixed per-kind adapter; never accept a client filesystem path."""
    header = request.headers.get('authorization', '')
    token = header[7:] if header.lower().startswith('bearer ') else ''
    identity = ai_access.authenticate(token)
    if not identity:
        raise HTTPException(401, 'Valid AI token required')
    from .ai_worker_registry import resolve_worker
    from .ai_metering_agent import execute_registered_worker
    from .ai_worker_protocol import WorkerUnavailable
    try:
        if resolve_worker(kind) is None:
            raise HTTPException(503, 'This AI model adapter is not installed or enabled')
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if request.headers.get('content-type', '').split(';')[0].strip().lower() not in ('audio/wav', 'audio/x-wav', 'application/octet-stream'):
        raise HTTPException(415, 'WAV content required')
    max_bytes = 32 * 1024 * 1024
    declared_length = request.headers.get('content-length', '0') or '0'
    if not declared_length.isdecimal():
        raise HTTPException(400, 'Invalid content length')
    if int(declared_length) > max_bytes:
        raise HTTPException(413, 'Input audio exceeds size limit')
    from .ai_remote_transport import decode_audio_options
    try:
        options = decode_audio_options(request.headers.get('x-mta-ai-options', ''))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > max_bytes:
            raise HTTPException(413, 'Input audio exceeds size limit')
    if not data:
        raise HTTPException(400, 'Empty audio input')
    from . import ai_request_dedup as dedup
    import json
    key = request.headers.get('x-mta-ai-idempotency-key', '')
    if key:
        try:
            digest = dedup.fingerprint(kind, json.dumps(options, sort_keys=True).encode(), bytes(data))
            dedup.admit(identity['user_id'], key, digest)
        except dedup.DuplicateAIRequest as exc:
            raise HTTPException(409, {'reason': 'duplicate_request', 'state': exc.state, 'job_id': exc.job_id}) from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
    try:
        result, meta = execute_registered_worker(identity['user_id'], kind, {'kind': kind, **options},
            token_id=identity['id'], source_wav=bytes(data))
    except WorkerUnavailable as exc:
        if key: dedup.finalize(identity['user_id'], key, state='failed')
        raise HTTPException(503, str(exc)) from exc
    except (ValueError, TypeError) as exc:
        if key: dedup.finalize(identity['user_id'], key, state='failed')
        raise HTTPException(400, str(exc)) from exc
    if key:
        from .ai_result_cache import save as save_result
        # Best effort: metering is already finalized; inability to retain a
        # response must not cause the same job to be run or billed twice.
        try:
            save_result(identity['user_id'], key, result, meta.get('media_type', 'audio/wav'), meta['job_id'])
        except (OSError, ValueError):
            pass
        dedup.finalize(identity['user_id'], key, job_id=meta['job_id'])
    if len(result) > max_bytes:
        raise HTTPException(413, 'AI result exceeds response limit')
    return Response(result, media_type=meta.get('media_type', 'audio/wav'), headers={'X-MTA-AI-Job-ID': meta['job_id']})
