"""Normalize installer device choices before Whisper; require an explicit close for popups."""
import sys
from types import SimpleNamespace
from pathlib import Path
import subprocess

import pytest
from app import music_text as mt

ROOT=Path(__file__).parents[1]


@pytest.mark.parametrize('configured,gpu,hip,expected',[
    ('auto',False,None,'cpu'),('auto',True,'7.2','cuda'),('rocm',True,'7.2','cuda'),
    ('cpu',True,'7.2','cpu'),('cuda:0',True,None,'cuda:0')])
def test_installer_choices_resolve_to_torch_devices(monkeypatch,configured,gpu,hip,expected):
    monkeypatch.setenv('MTA_AI_DEVICE',configured)
    monkeypatch.setitem(sys.modules,'torch',SimpleNamespace(cuda=SimpleNamespace(is_available=lambda:gpu),version=SimpleNamespace(hip=hip)))
    assert mt.native_ai_device()==expected


def test_explicit_rocm_unavailable_fails_without_cpu_fallback(monkeypatch):
    monkeypatch.setenv('MTA_AI_DEVICE','rocm')
    monkeypatch.setitem(sys.modules,'torch',SimpleNamespace(cuda=SimpleNamespace(is_available=lambda:True),version=SimpleNamespace(hip=None)))
    with pytest.raises(RuntimeError,match='ROCm requested but unavailable'):mt.native_ai_device()


def test_whisper_load_receives_resolved_auto_device(monkeypatch,tmp_path):
    import importlib.machinery
    monkeypatch.setenv('MTA_AI_DEVICE','auto');monkeypatch.setenv('MTA_LYRICS_MODEL_DIR',str(tmp_path))
    torch=SimpleNamespace(cuda=SimpleNamespace(is_available=lambda:True),version=SimpleNamespace(hip='7.2'))
    calls=[]
    def load(name,**kw):
        assert kw['device']=='cuda';calls.append(name)
        return SimpleNamespace(float=lambda:None,transcribe=lambda *a,**k:{'segments':[]})
    whisper=SimpleNamespace(__spec__=importlib.machinery.ModuleSpec('whisper',None),load_model=load)
    monkeypatch.setitem(sys.modules,'torch',torch);monkeypatch.setitem(sys.modules,'whisper',whisper)
    assert mt.extract_lyrics(tmp_path/'source.wav',require_inprocess=True)==[]
    assert calls==['turbo']


@pytest.mark.parametrize('mode,expected', [('open',0),('redraw',0),('unknown',0),('closed',1),('closed_after_terminal',0),('already_completed',0)])
def test_notices_require_explicit_early_close(mode,expected):
    script=r'''
const vm=require('vm'),assert=require('assert');
class Element{constructor(){this.children=[];this.dataset={};this.value='all';this.classList={toggle(){}};}set innerHTML(s){}append(...items){this.children.push(...items)}setAttribute(){}addEventListener(){}querySelectorAll(){return []}focus(){}}
const nodes={},root=new Element();root.querySelector=s=>nodes[s.slice(1)]||=(new Element());
const document={readyState:'complete',getElementById:()=>null,createElement:tag=>tag==='section'?root:new Element(),body:new Element()};
const callbacks={};let tick,done=false,acks=0;const mode=process.argv[2];
const job={job_id:'j',project_id:'p',operation:'download-chords-model',state:'running'};
const ctx={document,URLSearchParams,console,Date,Set,Map,Number,String,Error,JSON,location:{},localStorage:{getItem(){},setItem(){}},setTimeout:f=>{tick=f;return 1},clearTimeout(){},CustomEvent:class{},fetch:async(url,opt)=>{if(opt.method==='POST'){acks++;return {ok:true,json:async()=>({})}}return {ok:true,json:async()=>({actor_id:1,jobs:[],notifications:done?[{...job,state:'completed',completed_at:mode==='already_completed'?1:Date.now()/1000+100}]:[]})}}};
ctx.window={addEventListener:(t,f)=>(callbacks[t]||=[]).push(f),dispatchEvent(){},mtaPrepareAiTerminal:async()=>{}};
vm.createContext(ctx);vm.runInContext(process.argv[1],ctx);
const settle=()=>new Promise(r=>setImmediate(r));
(async()=>{await settle();let origin={isConnected:true,closest:()=>null};
if(mode!=='unknown')for(const cb of callbacks['mta:ai-job-accepted'])cb({detail:{...job,origin}});
await settle();
if(mode==='redraw'){origin.isConnected=false;origin={isConnected:true,closest:()=>null};ctx.window.mtaAiJobs.origin('j',origin);}
if(['closed','closed_after_terminal','already_completed'].includes(mode)){if(mode==='closed_after_terminal')ctx.window.mtaAiJobs.terminal('j');ctx.window.mtaAiJobs.closeOrigin(origin);origin.isConnected=false;}
done=true;await tick();await settle();assert.equal(acks,1);assert.equal(nodes['aj-notices']?.children.length||0,Number(process.argv[3]));
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result=subprocess.run(['node','-e',script,(ROOT/'app/static/ai_jobs.js').read_text(encoding='utf-8'),mode,str(expected)],capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stderr


def test_model_download_uses_close_aware_polling():
    js=(ROOT/'app/static/app.js').read_text(encoding='utf-8')
    section=js[js.index('async function pollModelDownloadJob('):js.index('async function startModelDownload')]
    assert 'return pollMediaJob(jobId,title,onDone)' in section
    assert 'closeOrigin' in js[js.index('function closeUtilityModal()'):js.index('function exportProjectArchive()')]
