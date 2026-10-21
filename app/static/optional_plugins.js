/* Same opt-in catalog in native settings and server administration. */
(()=>{'use strict';
const tr=(en,it)=>window.MtaLocale?.language==='it'?it:en;
async function api(path,body){const response=await fetch(path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json','X-MTA-Request':'1'},body:body?JSON.stringify(body):undefined,cache:'no-store'});const text=await response.text();let data;try{data=JSON.parse(text)}catch{throw Error(tr('Unexpected server response','Risposta inattesa del server')+' (HTTP '+response.status+'). '+(response.ok?'':text.replace(/<[^>]*>/g,' ').replace(/\s+/g,' ').slice(0,240)))}if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:tr('Request failed','Richiesta fallita')+' (HTTP '+response.status+')');return data}
const stateLabel=state=>({installed:tr('Installed','Installato'),not_installed:tr('Not installed','Non installato'),queued:tr('Waiting for installation','In attesa di installazione'),installing:tr('Installing','Installazione in corso'),failed:tr('Installation failed','Installazione fallita')})[state]||state;
const phaseLabel=stage=>({starting:tr('Starting','Avvio'),plugin:tr('Preparing plugin','Preparazione plugin'),download:tr('Downloading source','Download sorgente'),compile:tr('Compilation','Compilazione'),building:tr('Building','Compilazione'),command:tr('Running build tool','Esecuzione tool di compilazione'),install:tr('Installing files','Installazione file')})[stage]||stage;
window.openOptionalVst3=async function(host){
 if(!host){showUtilityModal(tr('Optional open-source VST3','VST3 open-source opzionali'),'<div id="optionalVst3Catalog"></div>');host=document.getElementById('optionalVst3Catalog')}
 const prefix=document.body.classList.contains('native-single-user')?'/api/native/optional-vst3':'/api/admin/optional-vst3';
 host.replaceChildren();const view={};host._optionalVst3View=view;
 const status=document.createElement('p');status.setAttribute('role','status');host.append(status);
 try{
  const data=await api(prefix);if(host._optionalVst3View!==view)return;
  const intro=document.createElement('p');intro.textContent=tr('Select plugins to compile and install. Builds require a C++ toolchain and may take several minutes. Progress shows actual build activity; the total duration cannot be predicted.','Selezionare i plugin da compilare e installare. Servono un toolchain C++ e diversi minuti. L’avanzamento mostra l’attività effettiva: la durata totale non è prevedibile.');host.prepend(intro);
  const reviewed=document.createElement('p');reviewed.textContent=tr('License review: ','Verifica licenze: ')+data.reviewed_at+(data.review_due?' · '+tr('Review overdue: new installations disabled','Revisione scaduta: nuove installazioni disabilitate'):'');host.append(reviewed);
  const all=document.createElement('button');all.textContent=tr('Select all available','Seleziona tutti i disponibili');host.append(all);const checks=[],cards=new Map();
  function paint(id,state){
   const card=cards.get(id);if(!card)return;
   card.box.dataset.state=state.state;if(card.remove){card.remove.hidden=state.state!=='installed';card.remove.disabled=false;}card.label.textContent=stateLabel(state.state);card.error.textContent=state.error||'';
   if(state.state==='installing'){
    if(!card.progress){card.progress=document.createElement('progress');card.progress.setAttribute('aria-label',tr('Installing ','Installazione ')+card.name);card.box.append(card.progress)}
    card.activity.textContent=phaseLabel(state.stage)+(state.message&&state.message!==id?' · '+state.message:'');
   }else{card.progress?.remove();card.progress=null;card.activity.textContent=''}
  }
  for(const category of [...new Set(data.plugins.map(p=>p.category))]){
   const section=document.createElement('details');section.open=true;section.className='optional-plugin-category';const title=document.createElement('summary');title.textContent=({'Reverb':tr('Reverb','Riverbero'),'Instruments / Synthesizers':tr('Instruments / Synthesizers','Strumenti / Sintetizzatori'),'Saturation / Tape':tr('Saturation / Tape','Saturazione / Nastro')})[category]||category;section.append(title);
   for(const plugin of data.plugins.filter(p=>p.category===category)){
    const card=document.createElement('article');card.className='optional-plugin-card';card.dataset.plugin=plugin.id;
    const label=document.createElement('label'),check=document.createElement('input');check.type='checkbox';check.value=plugin.id;check.disabled=!plugin.available;checks.push(check);label.append(check,document.createTextNode(plugin.name));
    const info=document.createElement('p');info.textContent=plugin.license+' · '+plugin.revision.slice(0,12);
    const badge=document.createElement('p');badge.className='optional-plugin-state';badge.setAttribute('role','status');
    const activity=document.createElement('p'),error=document.createElement('p');error.className='optional-plugin-error';
    const link=document.createElement('a');link.href=prefix+'/'+plugin.id+'/license';link.target='_blank';link.rel='noopener';link.textContent=tr('Read license','Leggi licenza');
    const source=document.createElement('a');source.href='https://github.com/'+plugin.repo+'/tree/'+plugin.revision;source.target='_blank';source.rel='noopener';source.textContent=tr('Source / build instructions','Sorgente / istruzioni compilazione');
    const remove=document.createElement('button');remove.type='button';remove.className='optional-plugin-uninstall';remove.textContent=tr('Uninstall','Disinstalla');
    remove.onclick=async()=>{remove.disabled=true;try{
     const plan=await api(prefix+'/'+plugin.id+'/uninstall');
     if(plan.in_use)throw Error(tr('Stop playback and close live plugin editors or monitoring before uninstalling.','Fermare la riproduzione e chiudere editor live o monitoring prima di disinstallare.'));
     const warning=plan.projects.length?'\n'+tr('Projects referencing this package: ','Progetti che utilizzano questo pacchetto: ')+plan.projects.length+'. '+tr('They will require reinstalling it or removing the affected inserts.','Richiederanno la reinstallazione o la rimozione degli insert interessati.'):'';
     if(!confirm(tr('Uninstall the complete package ','Disinstallare il pacchetto completo ')+plugin.name+'?'+warning))return;
     const result=await api(prefix+'/'+plugin.id+'/uninstall',{confirm:true,remove_build_cache:cleanup.checked});
     paint(plugin.id,{state:result.state});status.textContent=plugin.name+' · '+tr('Uninstalled','Disinstallato');
    }catch(e){error.textContent=e.message}finally{remove.disabled=false}};
    const cleanupLabel=document.createElement('label'),cleanup=document.createElement('input');cleanup.type='checkbox';cleanup.checked=true;cleanupLabel.className='optional-plugin-cleanup';cleanupLabel.append(cleanup,document.createTextNode(tr('Also remove downloaded sources and build cache','Rimuovi anche sorgenti scaricati e cache di compilazione')));
    card.append(label,info,badge,activity,error,link,document.createTextNode(' · '),source,remove,cleanupLabel);section.append(card);cards.set(plugin.id,{box:card,label:badge,activity,error,name:plugin.name,remove});paint(plugin.id,{state:plugin.state||(plugin.installed?'installed':'not_installed'),error:plugin.error});
   }host.append(section);
  }
  all.onclick=()=>{for(const check of checks)if(!check.disabled)check.checked=true};
  const consent=document.createElement('label'),accept=document.createElement('input');accept.type='checkbox';consent.append(accept,document.createTextNode(tr('I have reviewed the plugin licenses and want to install the selected plugins.','Ho consultato le licenze dei plugin e desidero installare quelli selezionati.')));
  const start=document.createElement('button');start.textContent=tr('Install selected VST3','Installa VST3 selezionati');host.append(consent,start);
  async function watch(job){
   start.disabled=true;all.disabled=true;for(const card of cards.values())card.remove.disabled=true;
   while(host.isConnected&&host._optionalVst3View===view){
    for(const [id,state] of Object.entries(job.plugins||{}))paint(id,state);if(job.state==='running')for(const card of cards.values())card.remove.disabled=true;
    if(job.state!=='running'){
     status.textContent=({completed:tr('Installation completed','Installazione completata'),completed_with_errors:tr('Installation completed with errors','Installazione completata con errori'),failed:tr('Installation failed','Installazione fallita')})[job.state]||job.state;
     start.disabled=false;all.disabled=false;for(const card of cards.values())card.remove.disabled=false;return;
    }
    status.textContent=tr('Installation in progress','Installazione in corso')+' · '+Math.round(Date.now()/1000-job.started_at)+'s';
    await new Promise(resolve=>setTimeout(resolve,1000));
    try{job=await api(prefix+'/jobs/'+job.id)}catch(e){status.textContent=tr('Connection interrupted; retrying: ','Connessione interrotta; nuovo tentativo: ')+e.message}
   }
  }
  start.onclick=async()=>{start.disabled=true;try{if(!accept.checked)throw Error(tr('Review and accept the licenses first','Consultare e accettare prima le licenze'));const selected=checks.filter(c=>c.checked&&!c.disabled).map(c=>c.value);await watch(await api(prefix+'/install',{plugins:selected,accept_licenses:true}))}catch(e){status.textContent=e.message;start.disabled=false}};
  if(data.active_job)await watch(await api(prefix+'/jobs/'+data.active_job));
 }catch(e){status.textContent=e.message}
};
window.addEventListener('DOMContentLoaded',()=>{const host=document.querySelector('[data-optional-vst3]');if(host){const button=host.querySelector('button');button?.addEventListener('click',()=>openOptionalVst3(host.querySelector('[data-catalog]')))}if(location.hash==='#optional-vst3')void openOptionalVst3()});
})();
