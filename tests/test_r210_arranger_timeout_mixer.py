"""Configurable bounded inference budgets and a bottom-anchored mixer dock."""
import io
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import wave
import pytest
from pydantic import ValidationError
from app.ai_arranger import RearrangeRequest, RemixRequest, prepare_plan
from app.ai_execution_limits import inference_timeout

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('cls', [RearrangeRequest, RemixRequest])
def test_budget_survives_plan_and_durable_request_roundtrip(cls):
    from app.models import Project
    request = cls(inference_timeout_seconds=7200)
    restored = cls.model_validate_json(request.model_dump_json())
    assert prepare_plan(Project(id='p',title='Test'),restored)['inference_timeout_seconds'] == 7200
    assert inference_timeout({}) == 3600


@pytest.mark.parametrize('value', [True, 0, 59, 14401, '3600', 3600.5])
def test_invalid_budgets_fail_closed(value):
    with pytest.raises(ValidationError): RearrangeRequest(inference_timeout_seconds=value)
    with pytest.raises(ValueError): inference_timeout({'inference_timeout_seconds':value})


def test_adapter_polls_past_old_limit_but_stops_at_custom_budget(monkeypatch,tmp_path):
    from app import ace_step_http_worker as w
    audio=io.BytesIO()
    with wave.open(audio,'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(44100);f.writeframes(b'\0\0'*441)
    source=tmp_path/'source.wav';source.write_bytes(audio.getvalue())
    plan=tmp_path/'request.json'
    clock=[0];polls=[];complete=[True]
    monkeypatch.setattr(w,'time',SimpleNamespace(monotonic=lambda:clock[0],sleep=lambda _:clock.__setitem__(0,clock[0]+400)))
    monkeypatch.setattr(w,'_source_path',lambda *_:source)
    monkeypatch.setattr(w,'endpoint_base',lambda:'http://127.0.0.1:8001')
    monkeypatch.setattr(w,'AceProcessMeter',lambda _:SimpleNamespace(sample=lambda:{}))
    monkeypatch.setattr(w,'_progress',lambda *a,**kw:None)
    monkeypatch.setattr(w,'_request',lambda url,*a,**kw:audio.getvalue() if '/v1/audio?' in url else b'{"data":{"task_id":"j"}}')
    def status(*a, **kwargs):
        polls.append(clock[0])
        return {'data':[{'task_id':'j','status':1,'result':[{'file':'/v1/audio?j'}]}]} if complete[0] and clock[0]>=1600 else {'data':[]}
    monkeypatch.setattr(w,'_json',status)
    monkeypatch.setenv('MTA_ACE_STEP_POLL_SECONDS','30')
    plan.write_text(json.dumps({'model_id':'ace-step-1.5','prompt':'orchestra','inference_timeout_seconds':3600}))
    w.run(plan,tmp_path/'output.wav')
    assert 1600 in polls and (tmp_path/'output.wav').read_bytes()==audio.getvalue()
    clock[0]=0;polls.clear();complete[0]=False
    plan.write_text(json.dumps({'model_id':'ace-step-1.5','prompt':'orchestra','inference_timeout_seconds':1200}))
    with pytest.raises(RuntimeError,match='timed out'): w.run(plan,tmp_path/'failed.wav')
    assert max(polls)<1200 and not (tmp_path/'failed.wav').exists()


@pytest.mark.parametrize('height', [240, 400])
@pytest.mark.parametrize('native', [False, True])
def test_mixer_resize_moves_top_and_keeps_bottom(height,native):
    wp=pytest.importorskip('weasyprint')
    css=(ROOT/'app/static/app.css').read_text()
    html=f'''<body class="{'native-single-user' if native else ''}"><main class="main-area" id="main" style="height:600px;width:900px;--mixer-height:{height}px"><section class="editor-zone" id="editor"></section><section class="mixer-dock" id="dock" style="height:{height}px"><div class="mixer-pane"><div class="dock-tabs">Mixer</div><div class="channels"><div class="channel">Channel</div></div></div></section></main></body>'''
    doc=wp.HTML(string=html,media_type='screen').render(stylesheets=[wp.CSS(string=css),wp.CSS(string='@page{size:1100px 900px;margin:0}')])
    boxes={}
    for b in doc.pages[0]._page_box.descendants():
        if b.element is not None: boxes.setdefault(b.element.get('id'),b)
    main,dock=boxes['main'],boxes['dock']
    # Border-box: bottom is fixed while increasing the height raises the top.
    assert dock.position_y == pytest.approx(600-height,abs=1)
    assert dock.position_y+dock.border_height() == pytest.approx(main.position_y+600,abs=1)


def test_arranger_posts_selected_budget_and_rejects_invalid_without_request():
    source=(ROOT/'app/static/app.js').read_text()
    section=source[source.index('async function planAiRemix('):source.index('let aiArrangerWatchTimer=null;')]
    js=r'''const vm=require('vm'),assert=require('assert');let sent=[];
const values={aiInferenceTimeoutMinutes:{value:'90'},aiRemixMode:{value:'rearrange'},aiRemixPlanResult:{isConnected:true},aiRemixScope:{value:'project'}};
const ctx={current:{id:'p'},document:{getElementById:id=>values[id]},api:async(url,opts)=>{sent.push(JSON.parse(opts.body));return{}},clearInterval(){}};
vm.createContext(ctx);vm.runInContext(process.argv[1],ctx);
(async()=>{await ctx.planAiRemix();assert.equal(sent[0].inference_timeout_seconds,5400);
values.aiInferenceTimeoutMinutes.value='241';await ctx.planAiRemix();assert.equal(sent.length,1);
assert.match(values.aiRemixPlanResult.textContent,/1–240/);
})().catch(e=>{console.error(e);process.exitCode=1});'''
    run=subprocess.run(['node','-e',js,section],capture_output=True,text=True,timeout=10)
    assert run.returncode==0,run.stderr


def test_custom_budget_reaches_cgroup_supervisor_without_changing_metering(monkeypatch,tmp_path):
    from app import ai_worker_protocol as protocol, ai_cgroup_metering, audio_engine
    from app.models import Project, Track
    worker=tmp_path/'worker.py';worker.write_text('# installed trusted worker')
    monkeypatch.setattr(protocol,'configured_worker',lambda:worker)
    monkeypatch.setenv('MTA_AI_CGROUP_PARENT','/delegated')
    def make_wav(path):
        with wave.open(str(path),'wb') as f:
            f.setnchannels(1);f.setsampwidth(2);f.setframerate(44100);f.writeframes(b'\0\0'*441)
    monkeypatch.setattr(audio_engine,'render_mix',lambda p,r,out,**kw:make_wav(out))
    def supervised(command,**kw):
        assert kw['timeout_seconds']==7200
        assert json.loads(Path(command[command.index('--request')+1]).read_text())['inference_timeout_seconds']==7200
        make_wav(command[command.index('--output')+1])
        return SimpleNamespace(exit_code=0,usage={'cpu_seconds':1.25})
    monkeypatch.setattr(ai_cgroup_metering,'run_cgroup_process',supervised)
    _,meta=protocol.run_worker_with_project_audio({'input_source':'master','inference_timeout_seconds':7200},
        Project(id='p',title='Test',tracks=[Track(id='t',name='Test',filename='t.wav')]),lambda *_:None)
    assert meta['_trusted_worker_source']=='cgroup'
    assert meta['_trusted_worker_usage']=={'cpu_seconds':1.25}


def test_compact_actual_channel_controls_fit_normal_dock_height():
    wp=pytest.importorskip('weasyprint')
    source=(ROOT/'app/static/app.js').read_text()
    section=source[source.index('function normalizeTrackGain(value){'):source.index('async function setAutoMix(')]
    js='''const vm=require('vm');const t={id:'t',name:'Track',volume_db:0,pan:0,channels:2,inserts:[]};
const ctx={current:{tracks:[t],realtime_meter_enabled:true},TRACK_COLORS:['blue'],clampPan:x=>x,panLabel:()=> 'Center',effectiveTrackChannels:()=>2,esc:s=>s,tr:en=>en};
vm.createContext(ctx);vm.runInContext(process.argv[1],ctx);process.stdout.write(ctx.channelHtml(t,0));'''
    run=subprocess.run(['node','-e',js,section],capture_output=True,text=True,timeout=10)
    assert run.returncode==0,run.stderr
    html='<section class="mixer-dock" style="height:280px!important;grid-template-columns:1fr"><div class="mixer-pane"><div class="dock-tabs">Mixer</div><div class="channels">'+run.stdout+'</div></div></section>'
    doc=wp.HTML(string=html,media_type='screen').render(stylesheets=[wp.CSS(string=(ROOT/'app/static/app.css').read_text()),wp.CSS(string='@page{size:1100px 900px;margin:0}')])
    boxes=[b for b in doc.pages[0]._page_box.descendants() if b.element is not None]
    channel=next(b for b in boxes if b.element.get('data-channel-track')=='t')
    value=next(b for b in boxes if b.element.get('id')=='mix-db-t')
    assert value.position_y+value.border_height()<=channel.position_y+channel.border_height()+1
    assert value.position_y+value.border_height()<280
