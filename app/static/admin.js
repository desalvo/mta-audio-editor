const q=s=>document.querySelector(s),qa=s=>[...document.querySelectorAll(s)];
function aiGpuStatusLabel(status){
  return ({host_agent_not_configured:'socket agente host non visibile nel container',
    host_agent_socket_missing:'socket assente: verificare servizio host e mount',
    host_agent_socket_missing_in_mount:'socket assente nel mount: agente fermo o mount obsoleto',
    host_agent_socket_access_denied:'accesso al socket agente host negato',
    host_agent_auth_unavailable:'credenziale agente host non accessibile',
    host_agent_unavailable:'agente host non disponibile',
    host_agent_mapping_unavailable:'agente host: identità processo non correlabile',
    host_agent_counter_unavailable:'agente host: contatore processo assente',pid_unavailable:'processo ACE non individuato',remote_endpoint:'backend remoto',
    process_unreadable:'processo ACE non accessibile',process_changed:'processo ACE riavviato',
    baseline_only:'raccolta campione iniziale',amd_smi_missing:'amd-smi non disponibile',
    amd_smi_failed:'lettura amd-smi fallita',amd_smi_timeout:'lettura amd-smi scaduta',
    amd_smi_invalid_json:'risposta amd-smi non valida',counter_unavailable:'contatore di processo assente',
    counter_reset:'contatore GPU azzerato',zero_counter_unverified:'contatore fermo a zero, non verificato',profiling:'profilazione in corso',profiled_kernels_diagnostic:'kernel GPU osservati, non fatturabili',profiler_no_gpu_events:'nessun kernel GPU rilevato',profiler_unavailable:'profiler non disponibile',profiler_failed:'profilazione non valida'
  })[status]||'telemetria non disponibile';
}
async function api(url,opt={}){opt.headers=opt.headers||{};if((opt.method||'GET').toUpperCase()!=='GET')opt.headers['X-MTA-Request']='1';const r=await fetch(url,opt);if(!r.ok)throw new Error(await r.text());return r.headers.get('content-type')?.includes('json')?r.json():r.text()}
function esc(s){return String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function fmtBytes(n){n=Number(n||0);if(n<1024)return n+' B';const u=['KB','MB','GB','TB'];let i=-1;do{n/=1024;i++}while(n>=1024&&i<u.length-1);return n.toFixed(n>=10?1:2)+' '+u[i]}

async function loadUsers(){if(window.mtaAccountLifecycle)window.mtaAccountLifecycle.loadAdmin();const users=await api('/api/admin/users');q('#usersBody').innerHTML=users.map(u=>`<tr data-user-id="${esc(u.id)}"><td><b>${esc(u.display_name||u.username)}</b><br><small>${esc(u.username)}</small><br><small>${u.social_providers?.length?'Social: '+esc(u.social_providers.join(', ')):'Locale'}</small></td><td>${esc(u.email)}<br>${u.email_confirmed?'<span class="badge ok">confermata</span>':'<span class="badge warn">non confermata</span>'}</td><td>${u.active?'<span class="badge ok">attivo</span>':'<span class="badge bad">non attivo</span>'}</td><td><select onchange="setRole(${u.id},this.value)"><option value="user" ${u.role==='user'?'selected':''}>Utente</option><option value="admin" ${u.role==='admin'?'selected':''}>Admin</option></select></td><td>${u.totp_enabled?'Sì':'No'}</td><td>${u.workspace_quota_bytes?fmtBytes(u.workspace_quota_bytes):'Illimitata'}</td><td>${!u.active?`<button class="approve" onclick="setActive(${u.id},true)" ${!u.email_confirmed?'disabled title="Email non confermata"':''}>Attiva</button>`:`<button onclick="setActive(${u.id},false)">Disattiva</button>`}<button class="danger" onclick="removeUser(${u.id},'${esc(u.username)}')">Elimina</button></td></tr>`).join('');window.mtaAdminLinkFocus?.()}
async function setActive(id,active){try{await api(`/api/admin/users/${id}`,{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify({active})});loadUsers()}catch(e){alert(e.message)}}
async function setRole(id,role){try{await api(`/api/admin/users/${id}`,{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify({role})});loadUsers()}catch(e){alert(e.message);loadUsers()}}
async function setQuota(id,mb){const n=Number(mb);if(!Number.isFinite(n)||n<0)return alert('Quota non valida');try{await api(`/api/admin/users/${id}`,{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify({workspace_quota_bytes:Math.round(n*1024*1024)})});await Promise.all([loadUsers(),loadStorage()])}catch(e){alert(e.message)}}
async function removeUser(id,name){if(!confirm(`Cancellare e disattivare ${name}? Billing e accounting saranno conservati. I progetti resteranno recuperabili entro il grace period configurato.`))return;try{await api(`/api/admin/users/${id}`,{method:'DELETE'});loadUsers();loadStorage()}catch(e){alert(e.message)}}

async function loadWebSettings(){loadSocialSettings();try{const d=await api('/api/admin/web-settings');q('#webSettingsSummary').innerHTML=`<div class="profile-row"><b>Versione</b><span>${esc(d.version)} · build ${esc(d.build)}</span></div><div class="profile-row"><b>Data directory</b><span><code>${esc(d.data_dir)}</code></span></div><div class="profile-row"><b>Upload massimo</b><span>${fmtBytes(d.max_upload_bytes)}</span></div><div class="profile-row"><b>Spazio disco libero</b><span>${fmtBytes(d.disk.free_bytes)} / ${fmtBytes(d.disk.total_bytes)}</span></div><div class="profile-row"><b>Modelli AI</b><span>${fmtBytes(d.models.total_bytes)} ${d.models.complete===false?'· rilevamento parziale':''}<br><small>${esc(d.models.note||'')}</small></span></div>`}catch(e){alert(e.message)}}
async function loadStorage(){try{const d=await api('/api/storage');q('#storageSummary').innerHTML=`<p><b>Disco:</b> ${fmtBytes(d.disk.used_bytes)} usati · ${fmtBytes(d.disk.free_bytes)} liberi · ${fmtBytes(d.disk.total_bytes)} totali</p><p><b>Modelli:</b> ${fmtBytes(d.models.total_bytes)} · Core ML ${fmtBytes(d.models.coreml_bytes)} · ONNX ${fmtBytes(d.models.onnx_bytes)} · server ${fmtBytes(d.models.server_bytes)}</p>`;q('#storageBody').innerHTML=(d.workspaces||[]).map(w=>`<tr><td><b>${esc(w.display_name||w.username)}</b><br><small>${esc(w.username)}</small></td><td>${fmtBytes(w.used_bytes)}</td><td>${w.quota_bytes?fmtBytes(w.quota_bytes):'Illimitata'}</td><td>${w.remaining_bytes==null?'—':fmtBytes(w.remaining_bytes)}</td><td>${w.percent==null?'—':w.percent+'%'}</td><td><input id="quota-${w.user_id}" type="number" min="0" step="100" value="${w.quota_bytes?Math.round(w.quota_bytes/1024/1024):0}" style="width:90px"> MB <button onclick="setQuota(${w.user_id},q('#quota-${w.user_id}').value)">Salva quota</button></td></tr>`).join('')}catch(e){alert(e.message)}}

async function loadSmtp(){const c=await api('/api/admin/smtp');const f=q('#smtpForm');for(const k of ['host','port','security','username','from_email','from_name'])if(f.elements[k])f.elements[k].value=c[k]??'';f.elements.password.placeholder=c.password_set?'Password salvata; lascia vuoto per mantenerla':'Password opzionale'}
q('#smtpForm').onsubmit=async e=>{e.preventDefault();const f=new FormData(e.target),d=Object.fromEntries(f);d.port=Number(d.port);try{await api('/api/admin/smtp',{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify(d)});alert('Configurazione salvata.');e.target.elements.password.value='';loadSmtp()}catch(x){alert(x.message)}}
async function testSmtp(){const f=new FormData(q('#smtpForm')),d=Object.fromEntries(f);d.port=Number(d.port);try{await api('/api/admin/smtp/test',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(d)});alert('Connessione SMTP riuscita.')}catch(e){alert(e.message)}}

async function loadModels(){try{const d=await api('/api/admin/demucs-models');q('#modelsBody').innerHTML=(d.models||[]).map(m=>`<tr><td><b>${esc(m.display_name||m.id)}</b><br><small>${esc(m.id)}</small></td><td>${esc(m.platform||'server')}</td><td>${m.stem_count||'—'}</td><td>${esc(m.version||'—')}</td><td><b>${m.size==null?'Da scaricare / dimensione non nota':fmtBytes(m.size)}</b></td><td>${m.installed?'<span class="badge ok">presente</span>':'<span class="badge warn">on-demand</span>'}</td><td>${m.blacklisted?'<span class="badge bad">blacklist</span>':'<span class="badge ok">consentito dal catalogo</span>'}</td><td>${m.blacklisted?`<button onclick="unblacklistModel('${esc(m.id)}')">Rimuovi blacklist</button>`:`<button onclick="forceModelUpdate('${esc(m.id)}')">${m.installed?'Forza update':'Scarica'}</button>${m.installed?` <button onclick="deleteLocalModel('${esc(m.id)}')">Cancella locale</button>`:''} <button class="danger" onclick="blacklistModel('${esc(m.id)}')">Blacklist</button>`}</td></tr>`).join('')}catch(e){alert(e.message)}}
async function updateAllModels(){try{await api('/api/admin/demucs-models/update',{method:'POST'});await Promise.all([loadModels(),loadStorage()])}catch(e){alert(e.message)}}
async function forceModelUpdate(id){try{await api('/api/admin/demucs-models/'+encodeURIComponent(id)+'/update',{method:'POST'});await Promise.all([loadModels(),loadStorage()])}catch(e){alert(e.message)}}
async function deleteLocalModel(id){if(!confirm('Cancellare solo la copia locale di '+id+'? Il modello resterà disponibile nel catalogo e potrà essere riscaricato.'))return;try{await api('/api/admin/demucs-models/'+encodeURIComponent(id)+'/local',{method:'DELETE'});await Promise.all([loadModels(),loadStorage()])}catch(e){alert(e.message)}}
async function blacklistModel(id){if(!confirm('Blacklist '+id+'? Il modello gestito verrà eliminato dallo storage server e nascosto ai client.'))return;try{await api('/api/admin/demucs-models/'+encodeURIComponent(id)+'/blacklist',{method:'POST'});await Promise.all([loadModels(),loadStorage()])}catch(e){alert(e.message)}}
async function unblacklistModel(id){try{await api('/api/admin/demucs-models/'+encodeURIComponent(id)+'/blacklist',{method:'DELETE'});await loadModels()}catch(e){alert(e.message)}}

qa('.settings-tabs button').forEach(b=>b.onclick=()=>{qa('.settings-tabs button').forEach(x=>x.classList.toggle('active',x===b));for(const tab of ['web','storage','users','smtp','models','aiQueue','diagnostics','legal']){const el=q('#'+tab+'Tab');if(el)el.hidden=b.dataset.tab!==tab}if(b.dataset.tab==='web')loadWebSettings();if(b.dataset.tab==='storage')loadStorage();if(b.dataset.tab==='users')loadUsers();const mail=q('#aiMailHost');if(mail)mail.hidden=b.dataset.tab!=='users';if(b.dataset.tab==='smtp')loadSmtp();if(b.dataset.tab==='legal')loadLegalSettings();if(b.dataset.tab==='models')loadModels();if(b.dataset.tab==='aiQueue')loadAIQueue();if(b.dataset.tab==='diagnostics')loadDiagnosticsSettings()});
// Initial load runs after all state and functions below are initialized.

// r208: Queue controls for the web Arranger/Remix jobs only.
let aiQueueRefreshTimer=null;
let aiQueueSettingsLoaded=false;
let queuePage=1,queueRequest=0,queuePages=1,queueManage=false;
const queueSelection=new Set();
function queueFilters(){return {search:q('#queueSearch').value.trim(),state:q('#queueState').value,visibility:q('#queueVisibility').value}}
function queueSearchChanged(){queuePage=1;queueSelection.clear();loadAIQueue()}
function queueManagement(){queueManage=!queueManage;q('#queueBulk').hidden=!queueManage;loadAIQueue()}
function queueSelectionLabel(){q('#queueSelected').textContent=queueSelection.size+' selezionati';q('#queuePageSelect').checked=false}
function queueSelect(id,on){if(on)queueSelection.add(id);else queueSelection.delete(id);queueSelectionLabel()}
function queueSelectPage(on){qa('#aiQueueBody input[type=checkbox]').forEach(el=>{if(!el.disabled){el.checked=on;if(on)queueSelection.add(el.value);else queueSelection.delete(el.value)}});queueSelectionLabel()}
async function loadAIQueue(){
  const serial=++queueRequest;
  try{
    const params=new URLSearchParams({...queueFilters(),page:queuePage,page_size:q('#queuePageSize').value});
    const d=await api('/api/admin/ai-execution/jobs?'+params);
    if(serial!==queueRequest)return;
    queuePage=d.page;queuePages=d.pages;
    q('#queuePageLabel').textContent=`Pagina ${d.page} di ${d.pages} · ${d.total} risultati`;
    q('#queuePrev').disabled=d.page<=1;q('#queueNext').disabled=d.page>=d.pages;
    if(!aiQueueSettingsLoaded){
      const settings=await api('/api/admin/ai-execution/settings');
      q('#aiQueueConcurrency').value=settings.max_concurrent_jobs;
      q('#aiArtifactMaxMiB').value=settings.max_artifact_mib;
      q('#aiArtifactMaxMiB').min=settings.artifact_mib_min;
      q('#aiArtifactMaxMiB').max=settings.artifact_mib_max;
      aiQueueSettingsLoaded=true;
    }
    const fmt=n=>n==null?'N/A':Number(n).toFixed(1)+' s';
    q('#aiQueueBody').innerHTML=(d.jobs||[]).map(j=>{
      const id=encodeURIComponent(j.job_id),active=['queued','blocked','running'].includes(j.state);
      return `<tr><td><input aria-label="Seleziona job ${esc(j.job_id)}" type="checkbox" value="${esc(j.job_id)}" ${!queueManage?'hidden':''} ${active||j.disposition==='deleted'?'disabled':''} ${queueSelection.has(j.job_id)?'checked':''} onchange="queueSelect(this.value,this.checked)"><code>${esc(j.job_id.slice(0,12))}</code><br>${esc(j.operation)}<br><small>Utente ${esc(j.actor_user_id||'—')}</small></td><td>${esc(new Date(j.created_at*1000).toLocaleString())}</td><td>${esc(j.project_id)}</td><td>${esc(j.state)}${j.disposition!=='enabled'?'<br><b>'+esc(j.disposition==='disabled'?'Disabilitato · escluso dai consumi':'Eliminato · escluso dai consumi')+'</b>':''}<br><small>${esc(j.message||'')}</small></td><td>${j.state==='queued'?j.queue_position:'—'}</td><td>${j.progress_percent==null?'—':Number(j.progress_percent).toFixed(0)+'%'}</td><td>CPU ${j.cpu_seconds!=null?fmt(j.cpu_seconds)+(j.resource_metrics_partial?' (verificata finora)':' (verificata)'):j.cpu_seconds_estimated!=null?'~'+fmt(j.cpu_seconds_estimated)+' (parziale, non fatturabile)':'N/A (misura non disponibile)'}<br>GPU ${j.gpu_seconds!=null?fmt(j.gpu_seconds):j.gpu_seconds_estimated!=null?'~'+fmt(j.gpu_seconds_estimated)+' (stima non fatturabile)':'N/A ('+esc(aiGpuStatusLabel(j.gpu_metrics_status))+')'}</td><td>${j.state==='queued'?`<button onclick="moveAIQueueJob('${id}',-1)">↑</button><button onclick="moveAIQueueJob('${id}',1)">↓</button>`:''}${active?`<button class="danger" onclick="cancelAIQueueJob('${id}')">Annulla</button>`:''}</td></tr>`;
    }).join('')||'<tr><td colspan="8">Nessun risultato</td></tr>';
    queueSelectionLabel();
  }catch(e){if(serial===queueRequest)q('#aiQueueBody').innerHTML='<tr><td colspan="8">'+esc(e.message)+'</td></tr>'}
}
function queueChangePage(delta){queuePage=Math.max(1,Math.min(queuePages,queuePage+delta));loadAIQueue()}
async function queueBulkAction(){
  const button=q('#queueApply');button.disabled=true;
  try{
    const body={ids:[...queueSelection],action:q('#queueAction').value,reason:q('#queueReason').value,filters:queueFilters()};
    const preview=await api('/api/admin/ai-execution/history',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({...body,preview:true})});
    if(!confirm(`${preview.count} job: ${body.action==='enable'?'ripristinare nei consumi e nel billing?':'escludere da accounting e billing?'} ${body.action==='delete'?'Le voci eliminate non saranno ripristinabili.':''} Misure e audit sono conservati. Le fatture chiuse non vengono modificate.`))return;
    await api('/api/admin/ai-execution/history',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)});
    queueSelection.clear();await loadAIQueue();
  }catch(e){alert(e.message)}finally{button.disabled=false}
}
async function saveAIQueueSettings(){
  try{await api('/api/admin/ai-execution/settings',{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify({max_concurrent_jobs:Number(q('#aiQueueConcurrency').value),max_artifact_mib:Number(q('#aiArtifactMaxMiB').value)})});await loadAIQueue()}catch(e){alert(e.message)}
}
async function cancelAIQueueJob(id){
  if(!confirm('Annullare il job? Un job GPU in corso potrebbe non fermarsi immediatamente.'))return;
  try{await api('/api/admin/ai-execution/jobs/'+id+'/cancel',{method:'POST'});await loadAIQueue()}catch(e){alert(e.message)}
}
async function moveAIQueueJob(id,delta){
  try{
    const d=await api('/api/admin/ai-execution/jobs?search='+id);const row=d.jobs.find(j=>j.job_id===decodeURIComponent(id));
    if(!row||row.queue_position==null)return;
    await api('/api/admin/ai-execution/jobs/'+id+'/move',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({position:row.queue_position+delta})});await loadAIQueue();
  }catch(e){alert(e.message)}
}


async function loadDiagnosticsSettings(){
  try {
    const settings=await api('/api/admin/diagnostics/settings');
    q('#diagnosticsEnabled').checked=!!settings.enabled;
    q('#diagnosticsStatus').textContent=settings.enabled?'Diagnostica abilitata':'Diagnostica disabilitata';
  }catch(e){q('#diagnosticsStatus').textContent=e.message}
}
async function saveDiagnosticsSettings(){
  try{
    const d=await api('/api/admin/diagnostics/settings',{
      method:'PUT',headers:{'content-type':'application/json'},
      body:JSON.stringify({enabled:q('#diagnosticsEnabled').checked})});
    q('#diagnosticsStatus').textContent=d.enabled?'Diagnostica abilitata':'Diagnostica disabilitata';
  }catch(e){q('#diagnosticsStatus').textContent=e.message}
}
async function downloadDiagnostics(){
  const status=q('#diagnosticsStatus');
  try{
    status.textContent='Preparazione archivio diagnostico...';
    const data=await api('/api/admin/diagnostics/bundles',{method:'POST'});
    const response=await fetch(data.url,{credentials:'same-origin'});
    if(!response.ok)throw new Error('Download failed: '+response.status);
    const blob=await response.blob(), url=URL.createObjectURL(blob);
    const a=document.createElement('a');a.href=url;a.download=data.name;
    document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(url);
    status.textContent='Archivio scaricato. Verrà eliminato dal server entro 24 ore.';
  }catch(e){status.textContent=e.message}
}

async function sendSmtpTest(){
  const button=q('#smtpSendTest');button.disabled=true;q('#smtpTestStatus').textContent='Invio in corso…';
  const configuration=Object.fromEntries(new FormData(q('#smtpForm')));configuration.port=Number(configuration.port);
  try{const d=await api('/api/admin/smtp/send-test',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({recipient:q('#smtpTestRecipient').value.trim(),configuration})});q('#smtpTestStatus').textContent=d.message}
  catch(e){q('#smtpTestStatus').textContent=e.message}finally{button.disabled=false}
}
async function loadSocialSettings(){
  if(!q('#socialProviders'))return;
  try{const d=await api('/api/admin/social-login');q('#socialEnabled').checked=d.enabled;q('#socialPublicUrl').value=d.public_url;
    q('#socialProviders').innerHTML=Object.entries(d.providers).map(([key,p])=>`<fieldset><legend>${esc(p.label)}</legend><label><input id="social-${key}-enabled" type="checkbox" ${p.enabled?'checked':''}> Abilita ${esc(p.label)}</label><label>Client ID / App ID<input id="social-${key}-id" value="${esc(p.client_id)}" autocomplete="off"></label><label>Client secret / App secret<input id="social-${key}-secret" type="password" autocomplete="new-password" placeholder="${p.secret_set?'Salvato: vuoto per mantenerlo':'Non configurato'}"></label><label><input id="social-${key}-clear" type="checkbox"> Rimuovi secret salvato</label><p><b>Callback da registrare nel provider:</b> <code>${esc(p.callback_url||'Imposta URL pubblico e salva')}</code></p><p>${p.ready?'Pronto per il test di accesso':'Disattivato o configurazione incompleta'}</p><p>${key==='google'?'Google Cloud → Google Auth Platform: Branding, Audience/test users, client Web application. Scope openid email profile.':key==='github'?'GitHub → Settings → Developer settings → OAuth Apps → New OAuth App. Scope read:user user:email, nessun accesso ai repository.':'Meta for Developers → app con Facebook Login web. Configura App Domains, Valid OAuth Redirect URIs, privacy policy, eliminazione dati e accessi email/public_profile; prova prima con utenti di test.'}</p></fieldset>`).join('');
  }catch(e){q('#socialStatus').textContent=e.message}
}
async function saveSocialSettings(){
  const providers={};for(const key of ['google','facebook','github'])providers[key]={enabled:q('#social-'+key+'-enabled').checked,client_id:q('#social-'+key+'-id').value,client_secret:q('#social-'+key+'-secret').value,clear_secret:q('#social-'+key+'-clear').checked};
  try{await api('/api/admin/social-login',{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify({enabled:q('#socialEnabled').checked,public_url:q('#socialPublicUrl').value,providers})});q('#socialStatus').textContent='Configurazione salvata. Prova il login da una finestra privata.';await loadSocialSettings()}catch(e){q('#socialStatus').textContent=e.message}
}

loadWebSettings();

const legalLabels={operator_name:'Titolare / prestatore: denominazione o nome completo',operator_address:'Indirizzo completo / sede',operator_country:'Paese di stabilimento',registration:'Registro, partita IVA o altri identificativi (se applicabili)',privacy_email:'Email privacy e diritti',support_email:'Email assistenza e reclami',dpo_contact:'DPO: recapiti, se designato',representative_contact:'Rappresentante UE/UK, se necessario',public_url:'URL pubblica HTTPS'};
const legalDisclosures={hosting:'Hosting: fornitore e Paesi di conservazione e accesso',processors:'Destinatari: nomi, ruoli, dati ricevuti; SMTP, SSO e AI esterna inclusi',transfers:'Trasferimenti fuori SEE: destinazioni, basi, garanzie e accesso a una copia; dichiarare anche se assenti',retention:'Conservazione: periodi/criteri e basi per account pendenti, contabilità, identità riservate, log, email, backup e quarantena; procedure per richieste privacy'};
async function loadLegalSettings(){
 try{const cfg=await api('/api/admin/legal-settings');const host=q('#legalFields');host.replaceChildren();
  for(const [key,label] of [...Object.entries(legalLabels),...Object.entries(legalDisclosures).flatMap(([key,label])=>['it','en'].map(lang=>[key+'_'+lang,label+' ('+lang.toUpperCase()+')']))]){
   const wrapper=document.createElement('label');wrapper.textContent=label;const large=key.endsWith('_it')||key.endsWith('_en');const input=document.createElement(large?'textarea':'input');input.id='legal-'+key;input.dataset.legalField=key;input.value=cfg[key]||'';input.maxLength=large?8000:1000;if(large)input.rows=5;else input.type=key.endsWith('email')?'email':key==='public_url'?'url':'text';wrapper.append(input);host.append(wrapper);
  }
  q('#legalEffectiveDate').value=cfg.effective_date;q('#legalReviewed').checked=cfg.reviewed;
  q('#legalStatus').textContent=cfg.ready?'Dati verificati dal gestore · revisione '+cfg.revision:'Documento da completare e verificare. Campi mancanti: '+(cfg.missing.join(', ')||'conferma della revisione');
  q('#legalForm').onsubmit=saveLegalSettings;
 }catch(e){q('#legalStatus').textContent=e.message}
}
async function saveLegalSettings(event){
 event.preventDefault();const data={reviewed:q('#legalReviewed').checked,effective_date:q('#legalEffectiveDate').value};for(const input of qa('[data-legal-field]'))data[input.dataset.legalField]=input.value;
 try{await api('/api/admin/legal-settings',{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify(data)});await loadLegalSettings()}catch(e){q('#legalStatus').textContent=e.message}
}
