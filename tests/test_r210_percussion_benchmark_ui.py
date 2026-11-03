"""Exercise the production benchmark UI without pretending to run a model."""
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'app/static/percussion_benchmark.js'


def node(checks):
    result = subprocess.run(['node'], input=HARNESS + SOURCE.read_text() + checks,
                            text=True, capture_output=True)
    assert result.returncode == 0, result.stderr


HARNESS = r'''
const assert=require('assert/strict');
const location={href:'https://mta.example.test/studio',origin:'https://mta.example.test'};
class Node{
 constructor(tag){this.tagName=tag.toUpperCase();this.children=[];this.listeners={};this.style={};this.attributes={};
 this.value='';this.checked=false;this.disabled=false;this.isConnected=true;this.src='';this.currentTime=0;this.duration=60;this.paused=true;this._text='';this.classes=new Set();this.clickCount=0;
 this.classList={add:(x)=>this.classes.add(x),contains:(x)=>this.classes.has(x)};}
 set textContent(x){this._text=String(x);this.children=[]}get textContent(){return this._text+this.children.map(x=>x.textContent||'').join(' ')}
 append(...nodes){for(const n of nodes){n.parentNode=this;this.children.push(n);if(this.tagName==='SELECT'&&this.children.length===1)this.value=n.value}}
 replaceChildren(...nodes){this.children=[];this._text='';this.append(...nodes)}
 setAttribute(k,v){this.attributes[k]=String(v)}removeAttribute(k){delete this.attributes[k];if(k==='src')this.src=''}
 addEventListener(name,fn,options){(this.listeners[name]??=[]).push({fn,once:options?.once})}
 removeEventListener(name,fn){this.listeners[name]=(this.listeners[name]||[]).filter(x=>x.fn!==fn)}
 async emit(name,extra={}){for(const item of [...(this.listeners[name]||[])]){if(item.once)this.removeEventListener(name,item.fn);await item.fn({currentTarget:this,target:this,preventDefault(){},...extra})}}
 click(){this.clickCount++;return this.emit('click')}load(){if(this.src)queueMicrotask(()=>this.emit('loadedmetadata'))}pause(){this.paused=true}async play(){this.paused=false}
 getContext(){return {clearRect(){},beginPath(){},moveTo(){},lineTo(){},stroke(){}}}
}
const document={createElement:tag=>new Node(tag),getElementById:()=>null};
const window={MtaLocale:{language:'it'}};
class FormData{constructor(){this.values=[]}append(...args){this.values.push(args)}}
const walk=n=>[n,...n.children.flatMap(walk)],find=(root,fn)=>walk(root).find(fn);
const byClass=(root,name)=>find(root,n=>(n.className||'').split(' ').includes(name));
const buttons=root=>walk(root).filter(n=>n.tagName==='BUTTON');
const calls=[];let created=false,ratingSaved=false,approval=null,additionalModels=[],additionalCampaigns=[];
const jsonResponse=value=>({ok:true,status:200,json:async()=>value});
const campaign={id:'campaign-one',title:'Campagna uno',kind:'experimental',status:'completed',counts:{total:2,completed:2}};
const details=()=>({campaign,cases:[{id:'case-one',title:'Shaker e hi-hat',group:'synthetic',category:'shaker'}],
 results:[{label:'Candidate A',model_name:'MODEL IDENTITY MUST STAY HIDDEN',identity_revealed:false,status:'completed',group:'synthetic',category:'shaker',metrics:{si_sdr_db:12.3,si_sdr_improvement_db:8,alignment:{samples:0,confidence:1}}}],
 ratings:ratingSaved?[{case_id:'case-one',candidate_label:'Candidate A',scores:{isolation:4,contamination:5,naturalness:4,transients:4,completeness:5,overall:4},decision:'limited',comment:'Shaker naturale'}]:[],approval});
async function fetch(url,options){
 calls.push({url,options});
 if(url.endsWith('/catalog'))return jsonResponse({models:[{id:'ready',name:'Model Ready',status:'ready',version:'v1',checkpoint_sha256:'a'.repeat(64),license:'MIT'},
  {id:'blocked',name:'Restricted',status:'not_authorized',reason:'No weight permission'},...additionalModels],datasets:[{id:'mta-synthetic-v1',name:'Synthetic',cases:24,prepared:true},{id:'real',name:'Real',cases:6,prepared:false}]});
 if(url.endsWith('/datasets/synthetic'))return jsonResponse({prepared:true});
 if(url.endsWith('/datasets/import'))return jsonResponse({prepared:true,id:'uploaded-recordings'});
 if(url.endsWith('/campaigns/restore'))return jsonResponse({campaign});
 if(url.endsWith('/campaigns')&&options.method==='POST'){created=true;return jsonResponse({campaign})}
 if(url.endsWith('/campaigns'))return jsonResponse({campaigns:created?[campaign,...additionalCampaigns]:[]});
 if(url.endsWith('/campaign-one/ratings')){ratingSaved=true;return jsonResponse({rating:{id:'rated'},identity:{name:'Model revealed after rating',version:'v1',checkpoint_sha256:'a'.repeat(64)}})}
 if(url.endsWith('/campaign-one/run'))return jsonResponse({campaign});
 if(url.endsWith('/campaign-one/approve')){approval={...approval,can_approve:true,state:'approved_manually'};return jsonResponse({approval})}
 if(url.endsWith('/models/configured/verify')){additionalModels[0].status='ready';return jsonResponse({verified:true})}
 if(url.endsWith('/models/configured/enabled')){additionalModels[0].enabled=JSON.parse(options.body).enabled;return jsonResponse({enabled:additionalModels[0].enabled})}
 if(url.includes('/campaign-one/blind?'))return jsonResponse({case:{id:'case-one',title:'Shaker e hi-hat',category:'shaker',description:'<img src=x onerror=alert(1)>',duration_seconds:60,excerpt:{start:10,end:25}},blind:true,
  input_url:'/api/admin/ai-benchmarks/campaigns/campaign-one/audio/input',reference_url:'/api/admin/ai-benchmarks/campaigns/campaign-one/audio/reference',
  candidates:[{label:'Candidate A',candidate_id:'opaque-a',audio_url:'/api/admin/ai-benchmarks/campaigns/campaign-one/audio/a',matched_audio_url:'/api/admin/ai-benchmarks/campaigns/campaign-one/audio/a-matched',peaks:[.1,.3,.7],rated:false},
  {label:'Candidate B',candidate_id:'opaque-b',audio_url:'/api/admin/ai-benchmarks/campaigns/campaign-one/audio/b',matched_audio_url:'/api/admin/ai-benchmarks/campaigns/campaign-one/audio/b-matched',peaks:[.2,.4,.8],rated:false}]});
 if(url.endsWith('/campaign-one'))return jsonResponse(details());
 if(url.endsWith('/campaign-two'))return jsonResponse({campaign:{id:'campaign-two',title:'Versione precedente'},results:[{rated:true,identity:{name:'Rated separator',version:'v0'},category:'shaker',status:'completed',metrics:{si_sdr_db:9}}]});
 throw Error('Unexpected URL '+url);
}
'''


def test_rating_validation_and_blind_identity_rules():
    node(r'''
const h=window.MtaBenchmark.helpers;
const values={scores:{isolation:1,contamination:5,naturalness:3,transients:4,completeness:2,overall:3},decision:'limited',comment:'  Test  '};
assert.deepEqual(h.validateRating(values),{scores:values.scores,decision:'limited',comment:'Test',explicit_approval:false});
for(const key of Object.keys(values.scores))for(const value of ['',null,0,6,2.5,'abc'])assert.throws(()=>h.validateRating({...values,scores:{...values.scores,[key]:value}}));
assert.throws(()=>h.validateRating({...values,decision:'approved'}));
assert.throws(()=>h.validateRating({...values,comment:'x'.repeat(4001)}));
assert.equal(h.validateRating({...values,comment:'x'.repeat(4000)}).comment.length,4000);
for(const explicit_approval of [undefined,false,'true',1])assert.throws(()=>h.validateRating({...values,decision:'professional',explicit_approval}));
assert.equal(h.validateRating({...values,decision:'professional',explicit_approval:true}).explicit_approval,true);
for(const decision of ['limited','rejected'])assert.throws(()=>h.validateRating({...values,decision,explicit_approval:true}));
assert.equal(h.candidateLabel({model_name:'SECRET',identity:{name:'SECRET'},label:'Candidate A'}),'Candidate A');
assert.equal(h.candidateLabel({model_name:'SECRET'}),'Candidato cieco');
assert.equal(h.candidateLabel({rated:true,identity:{name:'Known'}}),'Known');
assert.equal(h.candidateLabel({identity_revealed:true,model_id:'core-model',model_version:'v2'}),'core-model · v2');
assert.equal(h.candidateLabel({identity_revealed:false,model_id:'SECRET',model_version:'v2'}),'Candidato cieco');
assert.equal(h.statusLabel('approved_manually'),'Approvato manualmente');
assert.equal(h.categoryRows({'synthetic / shaker':{mean_si_sdr_db:8.25,n_metric:4}})[0].metrics.si_sdr_db,8.25);
assert.equal(h.statusLabel('not_installed'),'Non installato');
assert.equal(h.statusLabel('not_authorized'),'Non autorizzato');
assert.equal(h.statusLabel('invalid'),'Risultato non valido');
assert.equal(h.statusLabel('validated_automatically'),'Validato automaticamente');
assert.equal(h.statusLabel('inference_failed'),'Inferenza fallita');
assert.equal(h.statusLabel('invalid_result'),'Risultato non valido');
assert.equal(h.statusLabel('dataset_unavailable'),'Dataset non disponibile');
assert.equal(h.statusLabel('disabled'),'Disattivato');
''')


def test_audio_urls_and_excerpt_switching_remain_on_server_and_aligned():
    node(r'''
const h=window.MtaBenchmark.helpers;
for(const url of ['https://evil.example/audio.wav','javascript:alert(1)','data:audio/wav;base64,abc','/api/projects/private/audio','//evil.example/api/admin/ai-benchmarks/audio'])assert.equal(h.safeAudioUrl(url),null);
assert.equal(h.safeAudioUrl('/api/admin/ai-benchmarks/campaigns/x/audio/a'),'https://mta.example.test/api/admin/ai-benchmarks/campaigns/x/audio/a');
assert.deepEqual(h.excerptBounds({start:10,end:30},25),{start:10,end:25});
assert.deepEqual(h.excerptBounds({start:-2,end:20},12),{start:0,end:12});
assert.equal(h.switchPosition(15,{start:10,end:25},false),15);
assert.equal(h.switchPosition(0,{start:10,end:25},false),10);
assert.equal(h.switchPosition(50,{start:10,end:25},false),24.99);
assert.equal(h.switchPosition(50,{start:10,end:25},true),50);
''')


def test_production_ui_creates_campaign_with_explicit_models_options_and_server_protection():
    node(r'''
(async()=>{
 const host=new Node('div'),view=await window.MtaBenchmark.open(host);
 const setup=byClass(host,'benchmark-setup');
 const modelCards=walk(setup).filter(n=>n.className==='benchmark-model');
 const ready=find(modelCards[0],n=>n.tagName==='INPUT'),blocked=find(modelCards[1],n=>n.tagName==='INPUT');
 assert.equal(blocked.disabled,true);ready.checked=true;
 const seed=find(setup,n=>n.tagName==='INPUT'&&n.type==='number');seed.value='731';
 const kick=walk(setup).find(n=>n.tagName==='INPUT'&&n.type==='checkbox'&&n.parentNode.textContent.includes('Includi kick'));
 assert.equal(kick.checked,true);kick.checked=false;
 const kind=find(setup,n=>n.tagName==='SELECT'&&n.children.some(o=>o.value==='release'));kind.value='release';
 await buttons(setup).find(n=>n.textContent==='Crea campagna').click();
 const call=calls.find(c=>c.url.endsWith('/campaigns')&&c.options.method==='POST'),body=JSON.parse(call.options.body);
 assert.deepEqual(body.model_ids,['ready']);assert.deepEqual(body.dataset_ids,['mta-synthetic-v1']);
 assert.equal(body.kind,'release');assert.equal(body.seed,731);assert.equal(body.options.include_kick,false);
 assert.equal(body.options.clap,'excluded');assert.equal(body.options.timpani,'excluded');
 assert.equal(body.options.source_mode,'both');
 assert.equal(call.options.headers['X-MTA-Request'],'1');assert.equal(call.options.credentials,'same-origin');
 assert.ok(byClass(host,'benchmark-current').textContent.includes('Candidate A'));
 assert.ok(byClass(host,'benchmark-current').textContent.includes('0 campioni'));
 assert.ok(!byClass(host,'benchmark-current').textContent.includes('MODEL IDENTITY MUST STAY HIDDEN'));
 assert.ok(byClass(host,'benchmark-current').textContent.includes('Campagna sperimentale'));
 view.dispose();assert.equal(host._mtaBenchmarkDispose,undefined);
})().catch(e=>{console.error(e);process.exitCode=1});
''')


def test_blind_listening_audio_switch_level_matching_and_manual_rating_persistence():
    node(r'''
(async()=>{
 const host=new Node('div'),view=await window.MtaBenchmark.open(host);await view.openCampaign('campaign-one');await view.openCase('case-one');
 const panel=byClass(host,'benchmark-listening');
 assert.equal(walk(panel).filter(n=>n.tagName==='IMG').length,0);assert.ok(panel.textContent.includes('<img src=x onerror=alert(1)>'));
 assert.ok(!panel.textContent.includes('Model Ready'));assert.ok(!panel.textContent.includes('MODEL IDENTITY'));
 const audio=find(panel,n=>n.tagName==='AUDIO'),choices=byClass(panel,'benchmark-ab-choices');
 await buttons(choices).find(n=>n.textContent==='Candidate A').click();assert.equal(audio.currentTime,10);assert.equal(audio.paused,false);
 audio.currentTime=17.25;await buttons(choices).find(n=>n.textContent==='Candidate B').click();assert.equal(audio.currentTime,17.25);assert.ok(audio.src.endsWith('/b'));
 const playback=byClass(panel,'benchmark-playback'),labels=walk(playback).filter(n=>n.tagName==='LABEL');
 const matched=find(labels.find(n=>n.textContent.includes('livello comparabile')),n=>n.tagName==='INPUT');matched.checked=true;await matched.emit('change');
 assert.equal(audio.currentTime,17.25);assert.ok(audio.src.endsWith('/b-matched'));
 audio.currentTime=25;await audio.emit('timeupdate');assert.equal(audio.currentTime,10);
 const forms=walk(panel).filter(n=>n.tagName==='FORM'),first=forms[0];
 const fields=walk(first).filter(n=>n.tagName==='SELECT');for(let i=0;i<6;i++)fields[i].value=String(i===1?5:4);fields[6].value='limited';
 find(first,n=>n.tagName==='TEXTAREA').value='Shaker naturale, lieve hi-hat.';
 await first.emit('submit');
 const call=calls.find(c=>c.url.endsWith('/ratings')),body=JSON.parse(call.options.body);
 assert.equal(body.case_id,'case-one');assert.equal(body.candidate_id,'opaque-a');assert.equal(body.scores.contamination,5);
 assert.equal(body.decision,'limited');assert.equal(body.explicit_approval,false);assert.ok(!('model_id' in body));assert.ok(!('output_sha256' in body));
 assert.ok(first.textContent.includes('Model revealed after rating'));assert.ok(first.textContent.includes('a'.repeat(64)));
 assert.ok(byClass(host,'benchmark-current').textContent.includes('Shaker naturale'));
 view.dispose();assert.equal(audio.paused,true);
})().catch(e=>{console.error(e);process.exitCode=1});
''')


def test_restore_uses_multipart_and_resume_does_not_retry_verified_cases():
    node(r'''
(async()=>{
 const host=new Node('div'),view=await window.MtaBenchmark.open(host);await view.openCampaign('campaign-one');
 await buttons(byClass(host,'benchmark-current')).find(n=>n.textContent==='Esegui / riprendi casi pendenti').click();
 assert.deepEqual(JSON.parse(calls.find(c=>c.url.endsWith('/run')).options.body),{retry_failed:false});
 const restore=find(byClass(host,'benchmark-campaigns'),n=>n.tagName==='INPUT'&&n.type==='file');
 const archive={name:'campaign.zip'};restore.files=[archive];await restore.emit('change');
 const call=calls.find(c=>c.url.endsWith('/restore'));assert.ok(call.options.body instanceof FormData);
 assert.deepEqual(call.options.body.values,[['file',archive]]);assert.equal('Content-Type' in call.options.headers,false);
 assert.equal(call.options.headers['X-MTA-Request'],'1');
 view.dispose();
})().catch(e=>{console.error(e);process.exitCode=1});
''')


def test_installation_verification_and_activation_are_explicit_server_requests():
    node(r'''
(async()=>{
 additionalModels=[{id:'configured',name:'Configured candidate',status:'configured_unverified',enabled:true}];
 const host=new Node('div'),view=await window.MtaBenchmark.open(host);
 let card=walk(byClass(host,'benchmark-setup')).filter(n=>n.className==='benchmark-model')[2];
 assert.ok(card.textContent.includes('installazione non verificata'));
 await buttons(card).find(n=>n.textContent==='Verifica installazione').click();
 assert.ok(calls.find(c=>c.url.endsWith('/models/configured/verify')&&c.options.method==='POST'));
 card=walk(byClass(host,'benchmark-setup')).filter(n=>n.className==='benchmark-model')[2];
 assert.ok(card.textContent.includes('Pronto'));
 const enabled=walk(card).find(n=>n.tagName==='INPUT'&&n.parentNode.textContent.includes('Attivo per la selezione'));
 enabled.checked=false;await enabled.emit('change');
 const request=calls.find(c=>c.url.endsWith('/models/configured/enabled'));
 assert.equal(request.options.method,'PUT');assert.deepEqual(JSON.parse(request.options.body),{enabled:false});
 card=walk(byClass(host,'benchmark-setup')).filter(n=>n.className==='benchmark-model')[2];
 assert.equal(find(card,n=>n.tagName==='INPUT').disabled,true);
 view.dispose();
})().catch(e=>{console.error(e);process.exitCode=1});
''')


def test_final_approval_is_blocked_by_server_and_requires_explicit_confirmation():
    node(r'''
(async()=>{
 approval={can_approve:false,state:'awaiting_human_validation',blocked_reasons:['Six real recordings are missing.'],configuration_sha256:'b'.repeat(64)};
 const host=new Node('div'),view=await window.MtaBenchmark.open(host);await view.openCampaign('campaign-one');
 let review=byClass(host,'benchmark-final-approval');assert.ok(review.textContent.includes('Six real recordings are missing.'));
 assert.equal(buttons(review).length,0);assert.equal(calls.filter(c=>c.url.endsWith('/approve')).length,0);
 approval={can_approve:true,state:'awaiting_human_validation',configuration_sha256:'b'.repeat(64)};await view.openCampaign('campaign-one');
 review=byClass(host,'benchmark-final-approval');const consent=find(review,n=>n.tagName==='INPUT'),approve=buttons(review)[0];
 assert.equal(consent.checked,false);assert.equal(approve.disabled,true);
 consent.checked=true;await consent.emit('change');assert.equal(approve.disabled,false);
 find(review,n=>n.tagName==='TEXTAREA').value='I completed the full listening batch.';await approve.click();
 const request=calls.find(c=>c.url.endsWith('/approve'));assert.deepEqual(JSON.parse(request.options.body),{confirm:true,configuration_sha256:'b'.repeat(64),comment:'I completed the full listening batch.'});
 assert.equal(calls.filter(c=>c.url.endsWith('/approve')).length,1);
 assert.ok(byClass(host,'benchmark-final-approval').textContent.includes('Approvazione esplicita registrata'));
 assert.equal(buttons(byClass(host,'benchmark-final-approval')).length,0);
 view.dispose();
})().catch(e=>{console.error(e);process.exitCode=1});
''')


def test_cross_campaign_version_comparison_preserves_blinding_for_unrated_outputs():
    node(r'''
(async()=>{
 created=true;additionalCampaigns=[{id:'campaign-two',title:'Versione precedente',kind:'release',status:'completed'}];
 const host=new Node('div'),view=await window.MtaBenchmark.open(host);await view.openCampaign('campaign-one');
 const panel=byClass(host,'benchmark-current'),selector=find(panel,n=>n.tagName==='SELECT'&&n.attributes['aria-label']==='Campagna o versione del modello da confrontare');
 selector.value='campaign-two';await buttons(panel).find(n=>n.textContent==='Confronta campagne / versioni dei modelli').click();
 const comparison=byClass(panel,'benchmark-version-comparison');
 assert.ok(comparison.textContent.includes('Campagna uno'));assert.ok(comparison.textContent.includes('Versione precedente'));
 assert.ok(comparison.textContent.includes('Rated separator · v0'));assert.ok(comparison.textContent.includes('Candidate A'));
 assert.ok(!comparison.textContent.includes('MODEL IDENTITY MUST STAY HIDDEN'));assert.ok(comparison.textContent.includes('12.3'));assert.ok(comparison.textContent.includes('9'));
 view.dispose();
})().catch(e=>{console.error(e);process.exitCode=1});
''')


def test_dataset_import_requires_fresh_rights_confirmation_before_picker_and_upload():
    node(r'''
(async()=>{
 const host=new Node('div'),view=await window.MtaBenchmark.open(host);
 const setup=byClass(host,'benchmark-setup'),picker=find(setup,n=>n.tagName==='INPUT'&&n.type==='file');
 const consent=walk(setup).find(n=>n.tagName==='INPUT'&&n.type==='checkbox'&&n.parentNode.textContent.includes('Ho i diritti'));
 const start=buttons(setup).find(n=>n.textContent==='Importa dataset di registrazioni ZIP');
 assert.equal(consent.checked,false);assert.equal(picker.hidden,true);assert.equal(picker.accept,'.zip,application/zip');
 const before=calls.length;await start.click();
 assert.equal(picker.clickCount,0);assert.equal(calls.length,before);
 assert.ok(byClass(host,'benchmark-status').textContent.includes('Conferma i diritti'));
 // A forced change event must not bypass the same rights check.
 const archive={name:'authorized-recordings.zip'};picker.files=[archive];await picker.emit('change');
 assert.equal(calls.length,before);assert.equal(calls.filter(c=>c.url.endsWith('/datasets/import')).length,0);
 consent.checked=true;await start.click();assert.equal(picker.clickCount,1);
 await picker.emit('change');
 const request=calls.find(c=>c.url.endsWith('/datasets/import'));
 assert.ok(request.options.body instanceof FormData);
 assert.deepEqual(request.options.body.values,[['file',archive],['acknowledge_rights','true']]);
 assert.equal(request.options.method,'POST');assert.equal(request.options.headers['X-MTA-Request'],'1');
 assert.equal(request.options.credentials,'same-origin');assert.equal('Content-Type' in request.options.headers,false);
 assert.equal(consent.checked,false);assert.equal(picker.value,'');
 const freshConsent=walk(byClass(host,'benchmark-setup')).find(n=>n.tagName==='INPUT'&&n.type==='checkbox'&&n.parentNode.textContent.includes('Ho i diritti'));
 assert.equal(freshConsent.checked,false);
 assert.ok(byClass(host,'benchmark-status').textContent.includes('approvazione umana della qualità rimane distinta'));
 view.dispose();
})().catch(e=>{console.error(e);process.exitCode=1});
''')


def test_source_mode_default_and_explicit_alternatives_are_sent_without_extra_inference():
    node(r'''
(async()=>{
 for(const mode of ['drums','mix']){
  const host=new Node('div'),view=await window.MtaBenchmark.open(host),setup=byClass(host,'benchmark-setup');
  const model=walk(setup).find(n=>n.tagName==='INPUT'&&n.value==='ready');model.checked=true;
  const source=find(setup,n=>n.tagName==='SELECT'&&n.children.some(o=>o.value==='both'));
  assert.equal(source.value,'both');assert.deepEqual(source.children.map(o=>o.value),['both','drums','mix']);
  source.value=mode;const before=calls.length;
  await buttons(setup).find(n=>n.textContent==='Crea campagna').click();
  const requests=calls.slice(before),create=requests.find(c=>c.url.endsWith('/campaigns')&&c.options.method==='POST');
  assert.equal(JSON.parse(create.options.body).options.source_mode,mode);
  assert.equal(requests.some(c=>c.url.endsWith('/run')),false);
  assert.equal(requests.some(c=>c.url.endsWith('/approve')),false);
  view.dispose();
 }
})().catch(e=>{console.error(e);process.exitCode=1});
''')


def test_admin_template_loads_benchmark_and_opens_inline_without_daw_modal():
    template = (ROOT / 'app/templates/admin.html').read_text()
    script = re.search(r'<script src="(/static/percussion_benchmark\.js\?[^\"]+)"', template)
    stylesheet = re.search(r'<link rel="stylesheet" href="(/static/percussion_benchmark\.css\?[^\"]+)"', template)
    assert script and stylesheet
    assert script[1].split('?', 1)[1] == stylesheet[1].split('?', 1)[1]
    assert template.count('id="adminBenchmarkHost"') == 1
    opening = re.search(r'<button[^>]+onclick="([^"]+)"[^>]+aria-controls="adminBenchmarkHost"', template)
    assert opening
    assert template.index('id="modelsTab"') < template.index('id="percussionBenchmarkEntry"') < template.index('id="adminBenchmarkHost"')
    result = subprocess.run(['node'], input=HARNESS + SOURCE.read_text() + r'''
(async()=>{
 const host=new Node('div');let modalCalls=0;
 delete window.MtaLocale;document.documentElement={lang:'it'};
 document.getElementById=id=>id==='adminBenchmarkHost'?host:null;
 window.showUtilityModal=()=>{modalCalls++;throw Error('DAW modal must not be required by admin')};
 const MtaBenchmark=window.MtaBenchmark;
 await (async()=>{'''+opening[1]+r''';})();
 await new Promise(resolve=>setImmediate(resolve));
 assert.ok(byClass(host,'benchmark-setup'));assert.ok(host.textContent.includes('Benchmark e validazione AI'));assert.ok(host.textContent.includes('Model Ready'));
 assert.equal(modalCalls,0);assert.ok(calls.find(c=>c.url.endsWith('/catalog')));
 window.MtaBenchmark.close();
})().catch(e=>{console.error(e);process.exitCode=1});
''', text=True, capture_output=True)
    assert result.returncode == 0, result.stderr


def test_professional_excerpt_consent_is_never_automatic_and_never_approves_campaign():
    node(r'''
(async()=>{
 const host=new Node('div'),view=await window.MtaBenchmark.open(host);await view.openCampaign('campaign-one');await view.openCase('case-one');
 const form=find(byClass(host,'benchmark-listening'),n=>n.tagName==='FORM');
 const fields=walk(form).filter(n=>n.tagName==='SELECT');for(let i=0;i<6;i++)fields[i].value='4';
 const row=walk(form).find(n=>n.classes.has('benchmark-professional-consent')),consent=find(row,n=>n.tagName==='INPUT');
 assert.equal(row.hidden,true);assert.equal(consent.checked,false);assert.equal(consent.disabled,true);
 fields[6].value='professional';await fields[6].emit('change');
 assert.equal(row.hidden,false);assert.equal(consent.checked,false);assert.equal(consent.disabled,false);assert.equal(consent.required,true);
 await form.emit('submit');assert.equal(calls.some(c=>c.url.endsWith('/ratings')),false);
 assert.ok(byClass(host,'benchmark-status').textContent.includes('Conferma esplicitamente'));
 consent.checked=true;await form.emit('submit');
 const body=JSON.parse(calls.find(c=>c.url.endsWith('/ratings')).options.body);
 assert.equal(body.decision,'professional');assert.equal(body.explicit_approval,true);
 assert.equal(calls.some(c=>c.url.endsWith('/approve')),false);assert.equal(consent.checked,false);
 consent.checked=true;fields[6].value='limited';await fields[6].emit('change');
 assert.equal(row.hidden,true);assert.equal(consent.checked,false);assert.equal(consent.disabled,true);
 fields[6].value='professional';await fields[6].emit('change');assert.equal(consent.checked,false);
 view.dispose();
})().catch(e=>{console.error(e);process.exitCode=1});
''')
