/* Original durable service drain; explicit controls, readback after response loss. */
(()=>{
  'use strict';
  const host=document.getElementById('serviceRegimePanel');if(!host)return;
  const it=document.documentElement.lang.startsWith('it');
  const w=it?{
    title:'Ammissioni del servizio',note:'Prima del cambio di regime sospendi le nuove ammissioni e attendi la chiusura del lavoro originale. Il drain non certifica le obbligazioni finanziarie. Dopo il cambio o il recupero, riapri esplicitamente il servizio.',
    refresh:'Aggiorna stato del servizio',begin:'Sospendi nuove ammissioni',resume:'Riapri ammissioni',upgrade:'Conferma passaggio al build corrente',
    loading:'Verifica ammissioni…',off:'Protocollo persistente non attivo. Il solo profilo locale ristretto non certifica il drain del servizio.',open:'Servizio aperto',draining:'Ammissioni sospese',ready:'Lavoro originale chiuso',pending:'Lavoro originale ancora da verificare',
    build:'Build diverso: completa il drain originale prima del passaggio esplicito al nuovo build.',unknown:'Stato non disponibile. Aggiorna prima di intervenire; nessuna nuova operazione viene avviata automaticamente.',
    generation:'Revisione drain',active:'Ammissioni aperte',obligations:'Attività pendenti',
    confirmBegin:'Sospendere le nuove richieste e i timer? Il lavoro già ammesso conserva la propria identità e deve completarsi.',
    confirmResume:'Riaprire il servizio usando il drain originale mostrato? Un passaggio di regime incompleto deve essere prima recuperato o annullato.',
    confirmUpgrade:'Confermare il passaggio esplicito del drain originale al build corrente? Tutto il lavoro originale deve essere chiuso.',
    uncertain:'Esito da verificare: aggiorna lo stato originale prima di riprovare. Nessuna seconda richiesta viene inviata automaticamente.'
  }:{
    title:'Service admission',note:'Before changing regime, stop new admissions and wait for original work to finish. A drain does not certify financial obligations. After the change or recovery, explicitly reopen service.',
    refresh:'Refresh service state',begin:'Stop new admissions',resume:'Reopen admissions',upgrade:'Confirm handoff to current build',
    loading:'Checking admissions…',off:'Persistent protocol inactive. The restricted local profile alone does not certify a service drain.',open:'Service open',draining:'Admissions stopped',ready:'Original work closed',pending:'Original work still requires verification',
    build:'Build differs: complete the original drain before explicitly handing off to the new build.',unknown:'State unavailable. Refresh before acting; no new operation is started automatically.',
    generation:'Drain revision',active:'Open admissions',obligations:'Pending activities',
    confirmBegin:'Stop new requests and timers? Previously admitted work keeps its original identity and must finish.',
    confirmResume:'Reopen service using the displayed original drain? An unfinished regime transition must first be recovered or cancelled.',
    confirmUpgrade:'Confirm explicit handoff of the original drain to the current build? All original work must be closed.',
    uncertain:'Outcome needs verification: refresh the original state before retrying. No second request is sent automatically.'
  };
  const box=document.createElement('section');box.dataset.serviceDrain='';box.style.overflowWrap='anywhere';
  const title=document.createElement('h3');title.textContent=w.title;
  const note=document.createElement('p');note.textContent=w.note;
  const status=document.createElement('p');status.dataset.serviceDrainStatus='';status.setAttribute('role','status');status.setAttribute('aria-live','polite');
  function button(text,key){const b=document.createElement('button');b.type='button';b.textContent=text;b.dataset.serviceDrainAction=key;return b;}
  const refresh=button(w.refresh,'refresh'),begin=button(w.begin,'begin'),resume=button(w.resume,'resume'),upgrade=button(w.upgrade,'upgrade');
  box.append(title,note,status,refresh,begin,resume,upgrade);host.prepend(box);
  let state=null,busy=false;
  function controls(){
    refresh.disabled=busy;
    begin.disabled=busy||!state?.enabled||state.phase!=='open'||!state.build_matches;
    resume.disabled=busy||!state?.enabled||state.phase!=='draining'||!state.build_matches||!!state.pending?.by_kind?.cutover_recovery;
    upgrade.hidden=!state?.enabled||state.build_matches;
    upgrade.disabled=busy||!state||state.phase!=='draining'||state.active_count!==0||!state.pending?.verified||state.pending.count!==0;
  }
  async function request(path,body){
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),15000);
    try{
    const response=await fetch('/api/admin/service-admission'+path,{method:body?'POST':'GET',credentials:'same-origin',cache:'no-store',headers:body?{'Content-Type':'application/json','X-MTA-Request':'1'}:{},body:body?JSON.stringify(body):undefined,signal:controller.signal});
    if(!response.ok)throw Error('Service state unavailable');
    const data=await response.json();
    if(typeof data.enabled!=='boolean')throw Error('Invalid service state');
    if(data.enabled&&(!['open','draining'].includes(data.phase)||!Number.isSafeInteger(data.generation)||data.generation<0||!Number.isSafeInteger(data.active_count)||data.active_count<0||typeof data.build_matches!=='boolean'||(data.phase==='draining'&&!/^[A-Za-z0-9_-]{8,100}$/.test(data.drain_id))))throw Error('Invalid original drain');
    return data;
    }finally{clearTimeout(timer);}
  }
  function show(data){
    const identity=value=>JSON.stringify([value?.phase,value?.generation,value?.pinned_build,value?.drain_id,value?.active_count,value?.pending?.count]);
    if(identity(state)!==identity(data))window.dispatchEvent(new Event('mta-service-drain-changed'));
    state=data;
    status.textContent=!state.enabled?w.off:(state.phase==='open'?w.open:w.draining)+' · '+w.generation+': '+state.generation+' · '+w.active+': '+state.active_count+' · '+w.obligations+': '+(state.pending?.verified&&Number.isSafeInteger(state.pending.count)?state.pending.count:'?');
    if(state.enabled&&state.phase==='draining')status.textContent+=' · '+state.drain_id+' · '+(state.drained?w.ready:w.pending);
    if(state.enabled&&!state.build_matches)status.textContent+=' · '+w.build;
  }
  async function load(){busy=true;controls();status.textContent=w.loading;try{show(await request(''));}catch(_){state=null;status.textContent=w.unknown;}finally{busy=false;controls();}}
  async function change(action){
    if(busy||!state?.enabled)return;
    const question=action==='begin'?w.confirmBegin:action==='resume'?w.confirmResume:w.confirmUpgrade;
    if(!confirm(question+' '+w.generation+': '+state.generation+(state.drain_id?' · '+state.drain_id:'')))return;
    const body=action==='upgrade'?{expected_generation:state.generation,expected_build:state.pinned_build,confirm:true}:
      {expected_generation:state.generation,draining:action==='begin',identifier:action==='begin'?'drain-'+crypto.randomUUID():state.drain_id,confirm:true};
    busy=true;controls();
    try{show(await request(action==='upgrade'?'/upgrade':'/change',body));window.dispatchEvent(new Event('mta-service-drain-changed'));}
    catch(_){state=null;status.textContent=w.uncertain;}
    finally{busy=false;controls();refresh.focus();}
  }
  refresh.onclick=load;begin.onclick=()=>change('begin');resume.onclick=()=>change('resume');upgrade.onclick=()=>change('upgrade');
  controls();load();
})();
