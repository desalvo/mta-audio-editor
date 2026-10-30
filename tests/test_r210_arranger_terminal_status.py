"""Execute production JS for failed jobs, stopped timers and request rejection."""
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_terminal_job_stops_activity_and_retry_restores_progress():
    source = (ROOT / 'app/static/app.js').read_text()
    section = source[source.index('let aiArrangerWatchTimer=null;'):source.index('async function generateAndAddAiRemix()')]
    js = r'''
const vm=require('vm'),assert=require('assert');
const bar={hidden:false,removeAttribute(key){delete this[key]}};
const panel={hidden:true,querySelector:()=>bar,setAttribute(k,v){this[k]=v}};
const elements={aiRemixJobProgress:panel,aiRemixJobHint:{},aiRemixJobLabel:{},
  aiRemixGenerateButton:{},aiRemixPlanResult:{},aiRemixJobElapsed:{}};
let next,scheduled=0,cleared=0,now=110000;
let reply={job_id:'j',state:'running',phase:'inference',started_at:100,elapsed_seconds:10};
const ctx={tr:(en,it)=>en,current:{id:'p'},document:{getElementById:id=>elements[id]},Date:{now:()=>now},
  api:async()=>reply,setTimeout(f){next=f;scheduled++;return 1},clearTimeout(){},
  setInterval:()=>2,clearInterval(){cleared++}};
vm.createContext(ctx);vm.runInContext(process.argv[1],ctx);
(async()=>{
  for(const state of ['failed','cancelled','interrupted']){
    reply={job_id:'j',state:'running',phase:'inference',started_at:100,elapsed_seconds:10};
    await vm.runInContext('aiArrangerWatchActive(true)',ctx);
    assert.equal(bar.hidden,false);assert.equal(elements.aiRemixGenerateButton.disabled,false);
    assert.match(elements.aiRemixJobHint.textContent,/Processing\./);
    const previous=scheduled;
    now=160000;
    reply={job_id:'j',state,phase:state,message:'ace_connection_refused',started_at:100,elapsed_seconds:11};
    await next();
    assert.equal(panel.hidden,false);assert.equal(bar.hidden,true);
    assert.equal(panel['aria-busy'],'false');
    assert.equal(elements.aiRemixGenerateButton.disabled,false);
    assert.doesNotMatch(elements.aiRemixJobHint.textContent,/Processing\.|Do not close/);
    assert.match(elements.aiRemixJobElapsed.textContent,/Trascorso: 11s/);
    assert.equal(scheduled,previous);
    now=500000;vm.runInContext('aiArrangerRenderElapsed()',ctx);
    assert.match(elements.aiRemixJobElapsed.textContent,/Trascorso: 11s/);
  }
  assert.ok(cleared>=3);
  vm.runInContext("aiArrangerRenderProgress({state:'completed'},true)",ctx);
  assert.equal(bar.hidden,false);assert.equal(bar.value,100);
  vm.runInContext("aiArrangerRenderProgress({state:'running'})",ctx);
  assert.equal(bar.hidden,false);assert.equal(bar.value,undefined);
  assert.equal(elements.aiRemixGenerateButton.disabled,true);
  assert.match(elements.aiRemixJobHint.textContent,/Processing\./);
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result = subprocess.run(['node', '-e', js, section], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


def test_submission_error_stops_animation_and_reenables_generate():
    source = (ROOT / 'app/static/app.js').read_text()
    section = source[source.index('async function planAiRemix('):source.index('async function generateAndAddAiRemix()')]
    js = r'''
const vm=require('vm'),assert=require('assert');let cleared=0;
const bar={removeAttribute(){}};
const elements={aiRemixJobProgress:{isConnected:true,querySelector:()=>bar},
  aiRemixGenerateButton:{isConnected:true},aiRemixPlanResult:{isConnected:true},
  aiRemixJobHint:{},aiRemixJobElapsed:{},aiRemixJobLabel:{},
  aiInferenceTimeoutMinutes:{value:'60'},aiRemixMode:{value:'rearrange'}};
const ctx={tr:(en,it)=>en,current:{id:'p'},document:{getElementById:id=>elements[id]},
  api:async()=>{throw Error('submission rejected')},setInterval:()=>1,clearInterval(){cleared++}};
vm.createContext(ctx);vm.runInContext(process.argv[1],ctx);
(async()=>{
  await vm.runInContext("planAiRemix('generate-and-add')",ctx);
  assert.equal(elements.aiRemixGenerateButton.disabled,false);
  assert.equal(bar.hidden,true);assert.equal(cleared,1);
  assert.match(elements.aiRemixPlanResult.textContent,/submission rejected/);
  assert.doesNotMatch(elements.aiRemixJobHint.textContent,/Processing\.|Do not close/);
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result = subprocess.run(['node', '-e', js, section], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


def test_stale_status_and_reconciliation_never_update_another_project_or_close_new_observer():
    source = (ROOT / 'app/static/app.js').read_text()
    section = source[source.index('let aiArrangerWatchTimer=null;'):source.index('async function generateAndAddAiRemix()')]
    js = r'''
const vm=require('vm'),assert=require('assert');
(async()=>{
 for(const scenario of ['response','error','reconciliation']){
  let resolve,reject,rendered=0,closed=0;
  const pending=new Promise((a,b)=>{resolve=a;reject=b});
  const output={textContent:'new dialog'};
  const ctx={current:{id:'p'},document:{getElementById:()=>output},
   api:()=>pending,setTimeout:()=>1,clearTimeout(){},clearInterval(){},
   reconcileAiProject:async()=>vm.runInContext('aiArrangerWatchEpoch++',ctx),
   closeUtilityModal(){closed++},toast(){},window:{}};
  vm.createContext(ctx);vm.runInContext(process.argv[1],ctx);
  ctx.aiArrangerRenderProgress=()=>{rendered++};ctx.aiArrangerRenderElapsed=()=>{};
  const watched=ctx.aiArrangerWatchActive(true);
  if(scenario==='reconciliation')resolve({state:'completed',job_id:'old'});
  else{
   ctx.current={id:'different-project'};
   if(scenario==='error')reject(Error('old project network error'));
   else resolve({state:'completed',job_id:'old'});
  }
  await watched;
  assert.equal(closed,0);
  if(scenario!=='reconciliation'){
   assert.equal(rendered,0);assert.equal(output.textContent,'new dialog');
   assert.equal(vm.runInContext('aiArrangerLastSnapshot',ctx),null);
  }
 }
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result = subprocess.run(['node', '-e', js, section], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
