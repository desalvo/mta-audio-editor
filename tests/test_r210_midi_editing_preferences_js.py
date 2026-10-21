"""Execute editing and lazy preference behavior in a JavaScript runtime."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_group_transforms_are_bounded_polyphonic_and_reproducible():
    source = r'''
const assert=require('assert'),m=require(process.argv[1]);
const notes=[{id:'a',start_ms:10,duration_ms:100,pitch:1,velocity:100,channel:0},{id:'b',start_ms:90,duration_ms:200,pitch:65,velocity:90,channel:0},{id:'c',start_ms:90,duration_ms:200,pitch:65,velocity:80,channel:1}],ids=new Set(['a','b']);
const before=JSON.stringify(notes),moved=m.transform(notes,ids,'move',{value:-200});
assert.equal(moved[0].start_ms,0);assert.equal(moved[1].start_ms,80);assert.equal(moved[2].start_ms,90);
assert.equal(m.transform(notes,ids,'transpose',{value:-12})[1].pitch,64);
assert.deepEqual(m.transform(notes,ids,'humanize',{value:5,seed:42}),m.transform(notes,ids,'humanize',{value:5,seed:42}));
assert.notDeepEqual(m.transform(notes,ids,'humanize',{value:5,seed:42}),m.transform(notes,ids,'humanize',{value:5,seed:43}));
assert.equal(m.transform(notes,new Set(['a','b','c']),'join').length,3);
const split=m.transform(notes,new Set(['b']),'split',{value:200,uid:()=> 'right'});
assert.equal(split.length,4);assert.equal(split.find(n=>n.id==='b').duration_ms,110);assert.equal(split.find(n=>n.id==='right').duration_ms,90);
assert.equal(JSON.stringify(notes),before);assert.throws(()=>m.transform(notes,ids,'humanize',{velocity:NaN}));
'''
    result = subprocess.run(['node', '-e', source, str(ROOT/'app/static/midi_editing.js')], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


def test_lazy_preferences_batch_retry_and_inflight_changes_are_not_lost():
    source = r'''
const vm=require('vm'),fs=require('fs'),assert=require('assert'),disk=new Map(),calls=[];let resolve;
const ctx={TextEncoder,console,JSON,Object,Map,setTimeout:()=>1,clearTimeout(){},document:{getElementById:()=>({textContent:JSON.stringify({owner:'user:7',values:{theme:'dark'}})})},fetch:async(url,options)=>{calls.push(JSON.parse(options.body).values);return new Promise(r=>resolve=r)}};
ctx.window={localStorage:{getItem:k=>disk.get(k)||null,setItem:(k,v)=>disk.set(k,v)},addEventListener(){}};vm.createContext(ctx);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),ctx);const pref=ctx.window.MtaPreferences;
(async()=>{
 for(let i=0;i<130;i++)pref.setItem('mta.key.'+i,''+i);
 const first=pref.flush();assert.equal(calls.length,1);assert.equal(Object.keys(calls[0]).length,128);
 pref.setItem('mta.key.0','newer');resolve({ok:false,status:503});await first;
 assert.equal(pref.pending,130);assert.equal(pref.getItem('mta.key.0'),'newer');
 const second=pref.flush();resolve({ok:true});await second;
 const third=pref.flush();resolve({ok:true});await third;
 assert.equal(pref.pending,0);assert.equal(calls[1]['mta.key.0'],'newer');assert.equal(disk.get('mta.pending-preferences.user:7'),'{}');
 assert.throws(()=>pref.setItem('__proto__','x'));assert.throws(()=>pref.setItem('mta.huge','x'.repeat(32769)));
 pref.removeItem('theme');const removed=pref.flush();assert.equal(calls.at(-1).theme,null);resolve({ok:true});await removed;assert.equal(pref.getItem('theme'),null);
})().catch(error=>{console.error(error);process.exitCode=1});
'''
    result = subprocess.run(['node', '-e', source, str(ROOT/'app/static/user_preferences.js')], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


def test_native_legacy_preferences_migrate_without_copying_tokens_or_server_accounts():
    source = r'''
const vm=require('vm'),fs=require('fs'),assert=require('assert'),code=fs.readFileSync(process.argv[1],'utf8');
for(const owner of ['native','user:9']){
 const store=new Map([['mtaStemCount','6'],['mta.sidebar.collapsed.v1','{"midi":false}'],['mta.ai.token','secret-not-a-preference']]);
 const ctx={TextEncoder,JSON,Object,setTimeout:()=>1,clearTimeout(){},document:{getElementById:()=>({textContent:JSON.stringify({owner,values:{}})})}};
 ctx.window={localStorage:{get length(){return store.size},key:i=>[...store.keys()][i],getItem:k=>store.get(k)||null,setItem:(k,v)=>store.set(k,v)},addEventListener(){}};
 vm.createContext(ctx);vm.runInContext(code,ctx);const p=ctx.window.MtaPreferences;
 assert.equal(p.getItem('mta.ai.token'),null);
 assert.equal(p.getItem('mtaStemCount'),owner==='native'?'6':null);
}
'''
    result = subprocess.run(['node','-e',source,str(ROOT/'app/static/user_preferences.js')],capture_output=True,text=True,timeout=10)
    assert result.returncode == 0,result.stderr
