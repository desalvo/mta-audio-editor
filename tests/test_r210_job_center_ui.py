"""Execute the real monitor script with an isolated DOM/HTTP harness."""
from pathlib import Path
import subprocess

ROOT=Path(__file__).parents[1]


def test_background_monitor_notifies_after_origin_closed_and_acknowledges_once():
    script=r'''
const vm=require('vm'),assert=require('assert');
class Element{
 constructor(){this.dataset={};this.children=[];this.classList={toggle(){}};this.hidden=false;this.value='all';}
 set innerHTML(s){this.html=s;} get innerHTML(){return this.html;}
 append(...children){this.children.push(...children);for(const c of children)if(c&&typeof c==='object')c.parent=this;}
 setAttribute(k,v){this[k]=v;} addEventListener(){} querySelectorAll(){return [];} focus(){}
 remove(){if(this.parent)this.parent.children=this.parent.children.filter(c=>c!==this);}
}
const nodes={};const root=new Element();root.querySelector=selector=>{const id=selector.slice(1);if(!nodes[id]){nodes[id]=new Element();nodes[id].hidden=id==='aj-panel';}return nodes[id];};
const document={readyState:'complete',getElementById:()=>null,createElement:tag=>tag==='section'?root:new Element(),body:new Element()};
let tick,events=[],posts=[],terminal=false;const listeners={};
const job={job_id:'task',project_id:'p',operation:'arranger',state:'running',created_at:1,elapsed_seconds:2};
const store=new Map();
const ctx={document,URLSearchParams,console,Date,Set,Number,String,Map,Error,JSON,location:{},
setTimeout:fn=>{tick=fn;return 1;},clearTimeout(){},localStorage:{getItem:k=>store.get(k),setItem:(k,v)=>store.set(k,v)},
CustomEvent:class{constructor(type,init){this.type=type;this.detail=init.detail;}},
fetch:async(url,options)=>{if(options.method==='POST'){posts.push({url,body:JSON.parse(options.body)});return {ok:true,json:async()=>({ok:true})};}
const current={...job,state:terminal?'completed':'running'};return {ok:true,json:async()=>({actor_id:7,jobs:[current],active_count:terminal?0:1,total:1,notifications:terminal?[current]:[]})};}
};ctx.window={addEventListener:(k,fn)=>listeners[k]=fn,dispatchEvent:event=>events.push(event)};
vm.createContext(ctx);vm.runInContext(process.argv[1],ctx);
const settle=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
await settle();assert.equal(nodes['aj-panel'].hidden,true);assert.equal(events.length,0);assert.match(nodes['aj-launch'].textContent,/1/);
const origin={isConnected:true,closest:()=>null};ctx.window.mtaAiJobs.origin('task',origin);ctx.window.mtaAiJobs.closeOrigin(origin);origin.isConnected=false;
terminal=true;await tick();await settle();
assert.equal(nodes['aj-panel'].hidden,true);assert.equal(nodes['aj-notices'].children.length,1);
assert.equal(events[0].type,'mta:ai-terminal');assert.equal(events[0].detail.job_id,'task');
assert.equal(posts[0].url,'/api/ai-execution/notifications/ack');assert.deepEqual(posts[0].body.ids,['task']);
await tick();await settle();assert.equal(nodes['aj-notices'].children.length,1);assert.equal(events.length,1);
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result=subprocess.run(['node','-e',script,(ROOT/'app/static/ai_jobs.js').read_text()],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr


def test_arranger_tabs_keep_all_request_fields_and_native_tools_conditional():
    source=(ROOT/'app/static/app.js').read_text()
    section=source[source.index('async function openAiRemixPanel('):source.index('function aiArrangerTab(')]
    script=r'''
const vm=require('vm'),assert=require('assert');let html='',native=false;
const ctx={current:{id:'p',tracks:[{id:'t',name:'Test'}]},currentUser:{native_single_user:false},uiLanguage:'it',esc:String,toast(){},tr:a=>a,
api:async()=>({presets:[],models:[]}),showUtilityModal:(title,body)=>html=body,aiArrangerTab(){},aiArrangerWatchActive(){},aiAceRefresh:()=>native=true};
vm.createContext(ctx);vm.runInContext(process.argv[1],ctx);
(async()=>{await ctx.openAiRemixPanel();for(const id of ['aiPane-source','aiPane-arrangement','aiPane-execution','aiRemixModel','aiRemixPrompt','aiKeepChords','aiInferenceTimeoutMinutes','aiMeterCpu','aiMeterGpu'])assert.ok(html.includes('id="'+id+'"'),id);
assert.equal((html.match(/role="tab"/g)||[]).length,3);assert.ok(!html.includes('id="aiAceNativeTools"'));assert.ok(html.includes('Close and continue'));
ctx.currentUser.native_single_user=true;await ctx.openAiRemixPanel();assert.ok(html.includes('id="aiAceNativeTools"'));assert.equal(native,true);
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result=subprocess.run(['node','-e',script,section],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr


def test_token_page_admin_guard_navigation_and_no_inline_secret_storage(monkeypatch):
    from fastapi import FastAPI,HTTPException
    from fastapi.testclient import TestClient
    from app import ai_token_routes as routes
    api=FastAPI();api.include_router(routes.router);client=TestClient(api)
    monkeypatch.setattr(routes,'require_admin',lambda _:(_ for _ in ()).throw(HTTPException(403)))
    assert client.get('/admin/ai-tokens').status_code==403
    monkeypatch.setattr(routes,'require_admin',lambda _:None)
    page=client.get('/admin/ai-tokens')
    assert page.status_code==200
    assert 'href="/settings"' in page.text and 'href="/"' in page.text
    assert 'copyToken' in page.text and 'hideToken' in page.text
    js=(ROOT/'app/static/ai_tokens.js').read_text()
    assert "'x-mta-request':'1'" in js
    assert 'localStorage' not in js and 'innerHTML' not in js
