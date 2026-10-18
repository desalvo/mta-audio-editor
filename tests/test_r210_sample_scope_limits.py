"""Range-bound sample editing, physical workspace isolation and honest billing summary."""
import io
import os
import subprocess
import numpy as np
import pytest
import soundfile as sf
from fastapi import Request
from fastapi.testclient import TestClient
from app import auth, storage, main, ai_billing, ai_arranger_runtime, account_limits, audio_engine
from app.models import Clip, Track
from test_r210_decimal_bpm_shortcuts import function


@pytest.fixture
def accounts(tmp_path,monkeypatch):
    monkeypatch.setattr(auth,'DATA_ROOT',tmp_path/'auth');monkeypatch.setattr(storage,'ROOT',tmp_path/'projects')
    monkeypatch.setattr(ai_arranger_runtime,'_ROOT',tmp_path/'queue')
    monkeypatch.setenv('MTA_ADMIN_PASSWORD','administrator-password')
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH',raising=False)
    monkeypatch.delenv('MTA_NATIVE_SINGLE_USER',raising=False)
    auth.init_auth_db()
    with auth.db() as con:
        for name in ('personal','other'):
            con.execute("INSERT INTO users(username,email,password_hash,active,email_confirmed,role,created_at,updated_at,workspace_quota_bytes) VALUES(?,?, 'unused',1,1,'user',1,1,0)",(name,name+'@example.test'))
        users=[dict(r) for r in con.execute('SELECT * FROM users ORDER BY id')]
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False);monkeypatch.setattr(main,'check_basic_auth',lambda r:False)
    return users


def client_for(user):
    req=Request({'type':'http','headers':[(b'user-agent',b'testclient')]})
    c=TestClient(main.app,headers={'X-MTA-Request':'1'});c.cookies.set('mta_session',auth.create_session(user['id'],req));return c


def test_profile_limits_own_user_even_admin_and_unlimited(accounts):
    admin,personal,other=accounts
    p=storage.create_project('Personal',owner_user_id=personal['id']);q=storage.create_project('Other',owner_user_id=other['id'])
    storage.audio_path(p.id,'own.bin').write_bytes(b'x'*1234);storage.audio_path(q.id,'other.bin').write_bytes(b'x'*9999)
    client=client_for(personal);r=client.get('/api/account/limits?user_id='+str(other['id']))
    assert r.status_code==200,r.text
    d=r.json();assert d['user_id']==personal['id'] and d['storage']['project_count']==1
    assert d['storage']['used_bytes']==1234+(storage.pdir(p.id)/'project.json').stat().st_size
    assert d['storage']['quota_bytes'] is None and d['storage']['unlimited'] and d['storage']['remaining_bytes'] is None
    assert d['resources']['gpu']['verified_seconds'] is None
    assert d['billing']['outstanding_micro'] is None and d['billing']['payment_status']=='not-tracked'
    own_admin=client_for(admin).get('/api/account/limits').json()
    assert own_admin['user_id']==admin['id'] and own_admin['storage']['used_bytes']==0
    assert TestClient(main.app).get('/api/account/limits').status_code==401


def test_storage_deduplicates_hardlinks_and_does_not_follow_symlinks(accounts,tmp_path):
    user=accounts[1];a=storage.create_project('A',owner_user_id=user['id']);b=storage.create_project('B',owner_user_id=user['id'])
    src=storage.audio_path(a.id,'a.wav');src.write_bytes(b'x'*200)
    os.link(src,storage.audio_path(b.id,'b.wav'))
    outside=tmp_path/'outside.bin';outside.write_bytes(b'x'*99999)
    storage.audio_path(a.id,'unsafe.wav').symlink_to(outside)
    result=account_limits.project_storage(user['id'],[a,b],storage.pdir)
    assert result['audio_bytes']==200
    assert result['used_bytes']==200+sum((storage.pdir(p.id)/'project.json').stat().st_size for p in (a,b))
    assert main._workspace_usage_for_user(user['id'])==result['used_bytes']


def test_collapsed_preference_persists_only_for_current_account(accounts):
    a,b=accounts[1:];c=client_for(a)
    assert c.get('/api/session').json()['limits_expanded'] is False
    assert c.patch('/api/account',json={'limits_expanded':True}).status_code==200
    assert client_for(a).get('/api/session').json()['limits_expanded'] is True
    assert client_for(b).get('/api/session').json()['limits_expanded'] is False
    assert c.patch('/api/account',json={'limits_expanded':'false'}).status_code==400
    assert c.patch('/api/account',json={'limits_expanded':False}).status_code==200
    auth.init_auth_db();assert auth.public_user(auth.get_user(a['id']))['limits_expanded'] is False


def test_resource_totals_pending_closed_and_disabled_account(accounts,monkeypatch):
    uid=accounts[1]['id']
    from app import ai_billing_profiles
    monkeypatch.setattr(ai_billing_profiles,'suggested_prices',lambda:{'model_version':'test','cpu_model':None,'gpu_model':None,'suggested_micro_per_unit':{'cpu_seconds':0,'gpu_slot_seconds_estimated':0,'disk_gb_hours':0}})
    ai_billing.set_user_billing_enabled(uid,True);ai_billing.set_price('cpu_seconds',1000,valid_from=0);ai_billing.set_price('gpu_seconds',2000,valid_from=0)
    for start,cpu,gpu,state in ((10,2,3,'done'),(110,5,7,'done'),(130,11,13,'failed')):
        jid=ai_billing.create_job(uid,'test',started_at=start)
        ai_billing.finish_job(jid,state,{'cpu_seconds':cpu,'gpu_seconds':gpu},source='gpu-agent',finished_at=start+1)
    with auth.db() as con:
        con.execute("INSERT INTO ai_billing_periods(user_id,start_ts,end_ts,currency,total_micro,snapshot_json,created_at) VALUES(?,0,100,'EUR',8000,'{}',100)",(uid,))
    d=account_limits.summary(uid,{'used_bytes':0,'audio_bytes':0,'other_bytes':0,'project_count':0,'track_count':0},at=200)
    assert d['resources']['cpu']=={'verified_seconds':18,'diagnostic_seconds':None,'closed_seconds':2,'pending_seconds':5,'other_verified_seconds':11}
    assert d['resources']['gpu']['verified_seconds']==23 and d['resources']['gpu']['pending_seconds']==7
    assert d['billing']['pending_estimate_micro']==19000 and d['billing']['closed_total_micro']==8000
    assert d['billing']['outstanding_micro'] is None
    ai_billing.set_user_billing_enabled(uid,False)
    d=account_limits.summary(uid,d['storage'],at=200)
    assert d['billing']['pending_estimate_micro']==0 and d['resources']['gpu']['pending_seconds']==7


def test_actual_js_scope_zoom_clamping_and_extrema():
    setup="const assert=require('assert/strict');let sampleEditor;function tr(en){return en}const el={};function $(key){return el[key]||{}};function seDraw(){};"
    names=['seScope','seInitialWindow','seClamp','seSel','seZoom','sePosition','seZoomValue','seEnvelope','seExtrema']
    check=r'''
const info={sample_rate:1000,total_samples:10000,timeline_offset_ms:200};
const scope=seScope(info,{a:3200,b:1200});assert.deepEqual(scope,{start:1000,end:3000,restricted:true});
assert.throws(()=>seScope(info,{a:20000,b:30000}));
const view=seInitialWindow(info,scope,164,100,0);assert.deepEqual(view,{start:1000,end:2000});
const full=seInitialWindow(info,seScope(info,null),164,100,3200);assert.deepEqual(full,{start:3000,end:4000});
sampleEditor={info,scope,a:-100,b:20000,viewStart:1000,viewEnd:2000};assert.deepEqual(seSel(),[1000,3000]);
sePosition(-100);assert.equal(sampleEditor.viewStart,1000);sePosition(99999);assert.equal(sampleEditor.viewEnd,3000);
seZoom(0);assert.equal(sampleEditor.viewStart,1000);assert.equal(sampleEditor.viewEnd,3000);
seZoom(100);assert.equal(sampleEditor.viewEnd-sampleEditor.viewStart,4);
const samples=new Float32Array(512);samples[5]=1.1;samples[300]=.25;const buffer={numberOfChannels:1,getChannelData(){return samples}};
const s={scope:{start:256,end:512},buffer,env:seEnvelope(buffer)};assert.equal(seExtrema(s,256,512).hi,.25);
'''
    subprocess.run(['node','-e',setup+'\n'+'\n'.join(function(n) for n in names)+'\n'+check],check=True)


def test_range_audio_and_edit_preserve_gain_delay_and_timing(accounts,tmp_path):
    user=accounts[1];p=storage.create_project('Range',owner_user_id=user['id'])
    wave=.2*np.sin(2*np.pi*440*np.arange(44100)/44100);source=storage.audio_path(p.id,'tone.wav');sf.write(source,wave,44100,subtype='PCM_24')
    track=Track(id='tone',name='Tone',filename='tone.wav',duration_ms=1000,channels=1,gain_db=6,delay_ms=200,clips=[Clip(id='clip',source_start_ms=0,source_end_ms=1000,timeline_start_ms=100)])
    p.tracks=[track];storage.save_project(p);client=client_for(user);base=f'/api/projects/{p.id}/tracks/tone/sample-editor'
    before=tmp_path/'before.wav';audio_engine.render_track(track,source,before)
    info=client.get(base).json();assert info['total_samples']==48510 and info['timeline_offset_ms']==200
    audio=client.get(base+'/audio?start_sample=5000&end_sample=15000');assert audio.status_code==200,audio.text
    with sf.SoundFile(io.BytesIO(audio.content)) as f:
        assert len(f)==10000 and f.samplerate==44100
        assert np.max(np.abs(f.read()))==pytest.approx(.2,abs=.0001)
    assert client.get(base+'/audio?start_sample=-1').status_code==422
    assert client.get(base+'/audio?start_sample=20&end_sample=10').status_code==400
    response=client.post(base+'/effect-apply',json={'effect':'eq32','start_sample':5000,'end_sample':15000,'preset':'flat','params':{}})
    assert response.status_code==200,response.text
    edited=Track.model_validate(response.json()['track']);assert edited.gain_db==6 and edited.delay_ms==200 and edited.clips[0].timeline_start_ms==0
    after=tmp_path/'after.wav';audio_engine.render_track(edited,storage.audio_path(p.id,edited.filename),after)
    a=sf.read(before)[0];b=sf.read(after)[0];assert len(a)==len(b)
    np.testing.assert_allclose(a,b,atol=3/8388608)


def test_actual_canvas_dbfs_lines_and_full_scale_warning():
    setup=r'''const assert=require('assert/strict');let sampleEditor;const devicePixelRatio=1,window={MtaLocale:{language:'en'}};function tr(en){return en}
const strokes=[],texts=[],context={setTransform(){},fillRect(){},beginPath(){},moveTo(){},lineTo(){},stroke(){strokes.push(this.strokeStyle)},fillText(t){texts.push(t)}};
const elements={'#sampleCanvas':{clientWidth:164,clientHeight:200,getContext(){return context}}};function $(id){return elements[id]||(elements[id]={})}
'''
    check=r'''const samples=new Float32Array(100);samples[50]=1;const buffer={numberOfChannels:1,getChannelData(){return samples}};
sampleEditor={buffer,env:seEnvelope(buffer),scope:{start:0,end:100},info:{sample_rate:1000,total_samples:100,timeline_offset_ms:200},viewStart:0,viewEnd:100,a:0,b:100};
seDraw();assert.equal(texts.filter(x=>x==='0 dBFS').length,2);assert.equal(strokes.filter(x=>x==='#ffb04a').length,2);assert.ok(strokes.includes('#ff6969'));assert.ok(elements['#sePeakRead'].textContent.includes('possible clipping'));
'''
    subprocess.run(['node','-e',setup+'\n'+'\n'.join(function(n) for n in ('seEnvelope','seExtrema','seClamp','seSel','seZoomValue','seDraw'))+'\n'+check],check=True)


def test_actual_profile_panel_lazy_load_graphs_and_preference():
    from pathlib import Path
    script=r'''const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const elements={};function element(id){return elements[id]||(elements[id]={open:false,innerHTML:'',textContent:''})}
const resource={verified_seconds:2,closed_seconds:0,pending_seconds:2,other_verified_seconds:0,diagnostic_seconds:null};
const data={user_id:7,as_of:100,jobs:1,unmetered_jobs:0,storage:{used_bytes:1234,audio_bytes:1200,other_bytes:34,unlimited:true,quota_bytes:null,project_count:1,track_count:2},resources:{cpu:resource,gpu:{...resource,verified_seconds:null,pending_seconds:0}},billing:{enabled:false,pending_estimate_micro:0,closed_total_micro:0,closed_periods:0,outstanding_micro:null}};
const calls=[],context={window:{MtaLocale:{language:'en'},addEventListener(){}},document:{getElementById:element},Intl,fetch:async(url,opts={})=>{calls.push([url,opts]);return {ok:true,json:async()=>data}}};
vm.createContext(context);vm.runInContext(fs.readFileSync('app/static/account_limits.js','utf8'),context);
(async()=>{context.window.MtaAccountLimits.init({id:7,limits_expanded:false});assert.equal(calls.length,0);const details=element('accountLimits');details.open=true;details.ontoggle();for(let i=0;i<4;i++)await new Promise(setImmediate);
const html=element('accountLimitsContent').innerHTML;assert.ok(html.includes('Unlimited'));assert.ok(html.includes('1.205 KiB'));assert.ok(html.includes('Unavailable: payments are not recorded'));assert.equal((html.match(/<svg /g)||[]).length,4);const saved=calls.find(x=>x[1].method==='PATCH');assert.deepEqual(JSON.parse(saved[1].body),{limits_expanded:true});details.open=false;details.ontoggle();for(let i=0;i<4;i++)await new Promise(setImmediate);assert.equal(JSON.parse(calls.at(-1)[1].body).limits_expanded,false)})().catch(e=>{console.error(e);process.exitCode=1});
'''
    assert Path('app/static/account_limits.js').is_file()
    subprocess.run(['node','-e',script],check=True)


def test_all_profile_usage_is_inside_first_collapsible_panel(accounts):
    from html.parser import HTMLParser
    class Structure(HTMLParser):
        def __init__(self):super().__init__();self.stack=[];self.found=False;self.in_main=False;self.first=None
        def handle_starttag(self,tag,attrs):
            attrs=dict(attrs)
            if tag=='main':self.in_main=True
            if self.in_main and tag=='section' and self.first is None:self.first=attrs.get('class')
            if 'ai-resource-panel' in attrs.get('class',''):
                assert any(t=='details' and a.get('id')=='accountLimits' for t,a in self.stack)
                self.found=True
            if tag not in ('meta','input','link','img','br'):self.stack.append((tag,attrs))
        def handle_endtag(self,tag):
            if tag=='main':self.in_main=False
            for i in range(len(self.stack)-1,-1,-1):
                if self.stack[i][0]==tag:del self.stack[i:];break
    page=client_for(accounts[1]).get('/account')
    assert page.status_code==200
    parser=Structure();parser.feed(page.text)
    assert parser.found and 'account-limits' in parser.first
    assert 'id="storageSummary"' not in page.text
