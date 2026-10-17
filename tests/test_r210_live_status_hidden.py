"""No native-control flash before JS/session; active status replaces POST acknowledgement."""
from pathlib import Path
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('native', [False, True])
def test_hidden_controls_do_not_paint_without_javascript(native):
    wp = pytest.importorskip('weasyprint')
    css = (ROOT/'app/static/app.css').read_text()
    template = (ROOT/'app/templates/index.html').read_text()
    # Same controls/classes as the production template, including a visible native
    # save button to verify the additional server-mode guard independently.
    assert '<style>[hidden]{display:none!important}</style>' in template
    assert 'native-project-action native-only-action' in template
    html = '<body class="'+('native-single-user' if native else '')+'">'+'''
    <button id="hidden-nav" class="nav-item" hidden>Settings</button>
    <div id="hidden-editor" class="editor-content" hidden>Editor</div>
    <section id="hidden-mixer" class="mixer-dock" hidden>Mixer</section>
    <button id="native" class="nav-item native-only-action">Save</button>
    <button id="recent" class="nav-item">Open recent</button></body>'''
    doc = wp.HTML(string=html, media_type='screen').render(stylesheets=[wp.CSS(string=css)])
    ids = {b.element.get('id') for page in doc.pages for b in page._page_box.descendants() if b.element is not None}
    assert not {'hidden-nav', 'hidden-editor', 'hidden-mixer'} & ids
    assert ('native' in ids) == native
    assert 'recent' in ids


def test_actual_watcher_replaces_queued_and_reconnect_message():
    source = (ROOT/'app/static/app.js').read_text()
    section = source[source.index('let aiArrangerWatchTimer=null;'):source.index('async function generateAndAddAiRemix()')]
    js = r'''const vm=require('vm'),assert=require('assert');
const elements={aiRemixPlanResult:{textContent:'Job accepted: j · queued'},
aiRemixJobProgress:{querySelector:()=>null},aiRemixGenerateButton:{},aiRemixJobLabel:{},aiRemixJobElapsed:{}};
let next,reply={job_id:'j',state:'queued',phase:'queued'},fail=false;
const ctx={current:{id:'p'},document:{getElementById:id=>elements[id]},
api:async()=>{if(fail)throw Error('offline');return reply},
setTimeout:f=>{next=f;return 1},clearTimeout(){},setInterval:()=>1,clearInterval(){}};
vm.createContext(ctx);vm.runInContext(process.argv[1],ctx);
(async()=>{
 await vm.runInContext('aiArrangerWatchActive()',ctx);
 assert.match(elements.aiRemixPlanResult.textContent,/queued/);
 reply={job_id:'j',state:'running',phase:'inference',message:'Generating audio',
gpu_metrics_status:'zero_counter_unverified',gpu_metrics_source:'proxmox-host-amd-smi'};
 await next();
 assert.match(elements.aiRemixPlanResult.textContent,/running.*inference.*Generating audio/);
 assert.doesNotMatch(elements.aiRemixPlanResult.textContent,/queued/);
 assert.match(elements.aiRemixJobElapsed.textContent,/contatore fermo a zero.*host Proxmox \/ AMD-SMI/);
 assert.doesNotMatch(elements.aiRemixJobElapsed.textContent,/GPU: 0/);
 fail=true;await next();assert.match(elements.aiRemixPlanResult.textContent,/Connection interrupted/);
 fail=false;await next();assert.match(elements.aiRemixPlanResult.textContent,/running/);
 reply={job_id:'j',state:'completed',progress_percent:100};await next();
 assert.match(elements.aiRemixPlanResult.textContent,/completed/);
 assert.equal(elements.aiRemixGenerateButton.disabled,false);
})().catch(e=>{console.error(e);process.exitCode=1});'''
    run = subprocess.run(['node','-e',js,section], capture_output=True,text=True,timeout=10)
    assert run.returncode == 0, run.stderr
    assert "'Job accepted: '+plan.job_id+' · '+plan.state" not in source


def test_modal_never_inserts_native_setup_on_web_even_with_pending_status():
    source = (ROOT/'app/static/app.js').read_text()
    section = source[source.index('async function openAiRemixPanel('):source.index('async function planAiRemix(')]
    refresh = source[source.index('async function aiAceRefresh(){'):source.index('async function aiAceSaveConnection(){')]
    js = r'''const vm=require('vm'),assert=require('assert');let markup='',desktopRequests=0;
const ctx={document:{getElementById:()=>null},current:{id:'p',tracks:[]},currentUser:{native_single_user:false},uiLanguage:'en',
api:async url=>{if(url.includes('desktop-ace')){desktopRequests++;return new Promise(()=>{});}return {presets:[],models:[]}},
esc:s=>s,showUtilityModal:(title,html)=>{markup=html},aiAceRefresh:()=>{desktopRequests++},aiArrangerWatchActive(){}};
vm.createContext(ctx);vm.runInContext(process.argv[1],ctx);
(async()=>{
 await ctx.openAiRemixPanel();assert.doesNotMatch(markup,/aiAceNativeTools|aiAceInstallButton|aiAceRemoteToken/);
 assert.equal(desktopRequests,0);
 ctx.currentUser.native_single_user=true;await ctx.openAiRemixPanel();assert.match(markup,/aiAceNativeTools/);assert.equal(desktopRequests,1);
 ctx.currentUser.native_single_user=false;vm.runInContext(process.argv[2],ctx);await ctx.aiAceRefresh();assert.equal(desktopRequests,1);
})().catch(e=>{console.error(e);process.exitCode=1});'''
    run = subprocess.run(['node','-e',js,section,refresh],capture_output=True,text=True,timeout=10)
    assert run.returncode == 0, run.stderr
