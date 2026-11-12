"""GPU statistical views must update without changing billing or quotas."""
import json
from pathlib import Path
import subprocess

import pytest

from app import ai_arranger_runtime as queue, auth
from app.ai_compute_diagnostics import store, read
from app.ai_queue_usage import enrich
from test_r210_universal_queue_usage import ledger as ledger, add


def test_multistage_live_gpu_and_cpu_advance_beyond_last_checkpoint(ledger):
    add(ledger, source='gpu-kernel-verified', usage={'cpu_seconds':2, 'gpu_seconds':4}, evidence=4)
    add(ledger, ident='active-stage', status='running')
    store('active-stage', {'cpu_seconds_estimated':1, 'gpu_seconds_estimated':.5})
    sidecar = queue._ROOT / 'job.progress.json'
    sidecar.write_text(json.dumps({'cpu_seconds_estimated':3, 'gpu_seconds_estimated':2}))
    value = enrich({'actor_user_id':ledger,'job_id':'job','state':'running'})
    result = queue._with_live_progress(value)
    assert result['cpu_seconds_estimated'] == 5
    assert result['gpu_seconds_estimated'] == 6
    sidecar.write_text(json.dumps({'cpu_seconds_estimated':4, 'gpu_seconds_estimated':3}))
    result = queue._with_live_progress(enrich({'actor_user_id':ledger,'job_id':'job','state':'running'}))
    assert result['gpu_seconds_estimated'] == 7
    assert result.get('gpu_seconds') is None


def test_partial_diagnostic_sample_preserves_other_resource_and_allows_refinement(ledger):
    add(ledger)
    store('ledger', {'cpu_seconds_estimated':1, 'gpu_seconds_estimated':2})
    store('ledger', {'cpu_seconds_estimated':3})
    with auth.db() as con:
        assert read(con,ledger)['ledger'] == {'cpu_seconds_estimated':3, 'gpu_seconds_estimated':2}
    store('ledger', {'gpu_seconds_estimated':1})
    with auth.db() as con:
        assert read(con,ledger)['ledger'] == {'cpu_seconds_estimated':3, 'gpu_seconds_estimated':1}


@pytest.mark.parametrize('state', ['completed','failed','cancelled','interrupted'])
def test_missing_gpu_uses_fixed_statistical_duration_only(ledger, monkeypatch, state):
    with queue._db() as con:
        con.execute('UPDATE jobs SET state=?,started_at=100,completed_at=112.5 WHERE job_id=?', (state,'job'))
    before = auth.db_path().read_bytes()
    first = queue.get('job')
    monkeypatch.setattr(queue.time,'time',lambda:10000)
    second = queue.get('job')
    for result in [first,second]:
        assert result['gpu_statistics'] == {'seconds':12.5,'estimated':True,'source':'job-duration','billable':False}
        assert result['gpu_seconds'] is None and result['gpu_seconds_estimated'] is None
    assert auth.db_path().read_bytes() == before


def test_verified_zero_wins_over_duration_and_queued_job_has_zero_statistics(ledger):
    add(ledger,source='gpu-kernel-verified',usage={'gpu_seconds':0},evidence=0)
    result = queue.get('job')
    assert result['gpu_statistics']['seconds'] == 0
    assert result['gpu_statistics']['estimated'] is False
    result = queue._with_live_progress({'job_id':'not-started','state':'queued','created_at':1})
    assert result['gpu_statistics']['seconds'] == 0
    assert result['gpu_statistics']['source'] == 'not-started'


def test_statistical_projection_never_supplies_usage_to_settlement(ledger):
    value = queue._with_live_progress({'job_id':'isolated','state':'completed','started_at':1,'completed_at':11})
    assert value['gpu_statistics']['seconds'] == 10
    assert 'gpu_seconds' not in value and 'gpu_seconds_estimated' not in value
    with auth.db() as con:
        assert con.execute('SELECT count(*) FROM ai_compute_jobs').fetchone()[0] == 0


def test_job_center_includes_ledger_metrics_and_statistics(ledger):
    from app.ai_job_views import feed
    add(ledger,source='gpu-kernel-verified',usage={'gpu_seconds':3},evidence=3)
    value = feed(ledger,lambda pid:True)['jobs'][0]
    assert value['gpu_seconds'] == 3
    assert value['gpu_statistics']['seconds'] == 3
    assert value['gpu_statistics']['estimated'] is False


def test_parallel_sidecar_is_bound_to_original_stage_and_not_counted_twice(ledger):
    add(ledger,ident='first',status='running')
    add(ledger,ident='second',status='running')
    store('first',{'gpu_seconds_estimated':2})
    store('second',{'gpu_seconds_estimated':3})
    sidecar=queue._ROOT/'job.progress.json'
    sidecar.write_text(json.dumps({'_ledger_job_id':'second','gpu_seconds_estimated':7}))
    result=queue._with_live_progress(enrich({'actor_user_id':ledger,'job_id':'job','state':'running','started_at':1}))
    assert result['gpu_seconds_estimated']==9
    assert '_ledger_job_id' not in result and '_resource_live_context' not in result
    sidecar.write_text(json.dumps({'_ledger_job_id':'another-owner','gpu_seconds_estimated':999}))
    result=queue._with_live_progress(enrich({'actor_user_id':ledger,'job_id':'job','state':'running','started_at':1}))
    assert result['gpu_seconds_estimated']==5


def test_finished_component_totals_are_not_replaced_by_last_sidecar(ledger):
    add(ledger,source='gpu-kernel-verified',usage={'gpu_seconds':4},evidence=4)
    add(ledger,ident='second',source='gpu-kernel-verified',usage={'gpu_seconds':6},evidence=6)
    (queue._ROOT/'job.progress.json').write_text(json.dumps({'gpu_seconds_estimated':6}))
    result=queue._with_live_progress(enrich({'actor_user_id':ledger,'job_id':'job','state':'running','started_at':1}))
    assert result['gpu_seconds']==10
    assert result['gpu_statistics']['seconds']>=10


def test_report_finds_non_uuid_link_without_adding_queue_job_twice(ledger):
    from app.ai_usage_reporting import records, snapshot
    add(ledger,usage={'cpu_seconds':2})
    rows=records(ledger,0,10)
    assert len(rows)==1 and rows[0]['id']=='ledger'
    assert rows[0]['gpu_statistics']['seconds']==1
    total=snapshot(ledger,0,10)
    assert total['jobs']==1 and total['gpu_statistics']['seconds']==1
    assert total['usage']=={'cpu_seconds':2}


def test_running_fallback_advances_and_does_not_change_telemetry(tmp_path, monkeypatch):
    monkeypatch.setattr(queue,'_ROOT',tmp_path)
    clock=[110.]
    monkeypatch.setattr(queue.time,'time',lambda:clock[0])
    row={'job_id':'live','state':'running','started_at':100,'completed_at':None}
    assert queue._with_live_progress(row)['gpu_statistics']['seconds']==10
    clock[0]=113
    result=queue._with_live_progress(row)
    assert result['gpu_statistics']['seconds']==13
    assert 'gpu_seconds_estimated' not in result


def test_summary_includes_each_job_estimate_once_and_preserves_financial_usage(ledger):
    from app.ai_usage_reporting import snapshot
    result=snapshot(ledger,0,10)
    assert result['gpu_statistics']['seconds']==1
    assert result['gpu_statistics']['duration_estimated_jobs']==1
    assert result['usage']=={} and result['diagnostic']=={}
    assert result['credits_debited_micro']==0 and result['cost_micro']==0
    with auth.db() as con:
        assert con.execute('SELECT count(*) FROM ai_compute_jobs').fetchone()[0]==0


@pytest.mark.parametrize('language', ['it','en'])
def test_email_statistical_estimate_is_labeled_and_not_a_charge(language):
    from app.ai_notifications import render
    payload={'event':'terminal','status':'completed','job_id':'statistics-only','operation':'demucs',
        'started_at':100,'finished_at':112.5,'usage':{},'diagnostic':{},'amount_micro':0,
        'gpu_statistics':{'seconds':12.5,'estimated':True,'source':'job-duration','billable':False}}
    _,plain,html=render(payload,language)
    assert '~12.500 s' in plain and '~12.500 s' in html
    assert ('uso GPU non confermato' if language=='it' else 'GPU use unconfirmed') in plain
    assert '0.000000' in plain


def test_actual_job_renderer_and_modal_timer_show_statistical_fallback():
    root=Path(__file__).parents[1]
    source=(root/'app/static/ai_jobs.js').read_text()
    metrics=next(line for line in source.splitlines() if line.startswith('function metrics('))
    app=(root/'app/static/app.js').read_text()
    modal=app[app.index('let aiArrangerWatchTimer'):app.index('async function aiArrangerWatchActive')]
    script=r'''
const vm=require('vm'),assert=require('assert');
const context={esc:String,seconds:v=>v+'s',window:{MtaLocale:{language:'en'}}};
vm.createContext(context);vm.runInContext(process.argv[1],context);
assert(context.metrics({gpu_statistics:{seconds:12.5,estimated:true,source:'job-duration'}}).includes('GPU ~12.5s'));
assert(context.metrics({gpu_statistics:{seconds:12.5,estimated:true,source:'job-duration'}}).includes('GPU use unconfirmed'));
assert(context.metrics({gpu_statistics:{seconds:0,estimated:false,source:'measurement'}}).includes('GPU 0s'));
const elapsed={};let now=110000;
const modal={tr:(en,it)=>en,document:{getElementById:id=>id==='aiRemixJobElapsed'?elapsed:null},clearInterval(){},Date:{now:()=>now}};
vm.createContext(modal);vm.runInContext(process.argv[2],modal);
vm.runInContext("aiArrangerLastSnapshot={job_id:'job',state:'running',started_at:100,gpu_statistics:{seconds:5,estimated:true,source:'job-duration'}};aiArrangerRenderElapsed()",modal);
assert(elapsed.textContent.includes('GPU: ~10.0 s (Job duration estimate'));
now=113000;vm.runInContext('aiArrangerRenderElapsed()',modal);
assert(elapsed.textContent.includes('GPU: ~13.0 s'));
vm.runInContext("aiArrangerLastSnapshot={job_id:'job',state:'completed',elapsed_seconds:13,gpu_statistics:{seconds:2,estimated:false,source:'measurement'}};aiArrangerRenderElapsed()",modal);
assert(elapsed.textContent.includes('GPU: 2.0 s (Measured consumption)'));
'''
    result=subprocess.run(['node','-e',script,metrics,modal],capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stderr
