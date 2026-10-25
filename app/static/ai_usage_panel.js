/* User-scoped reports and digest settings; administrator selects an explicit account. */
(()=>{'use strict';
const choices=[['','Predefinita del server'],['day','Ogni giorno'],['week','Ogni settimana'],['month','Ogni 30 giorni'],['off','Nessun riepilogo']];
async function api(path,method='GET',body){const r=await fetch(path,{method,credentials:'same-origin',headers:{'content-type':'application/json','x-mta-request':'1'},body:body===undefined?undefined:JSON.stringify(body)});const d=await r.json();if(!r.ok)throw Error(typeof d.detail==='string'?d.detail:'Richiesta non riuscita');return d;}
const fmt=resources=>Object.entries(resources||{}).map(([k,v])=>k+': '+Number(v).toFixed(3)).join(' · ')||'Non disponibile';
function mount(root){const admin=root.dataset.admin==='true';root.innerHTML=`<h2>Risorse AI e riepiloghi email</h2><p>Le email dei job partono quando SMTP/SMTPS è configurato; i consumi per job accettati dal server sono contabilizzati per quote e billing. Questo riepilogo riguarda il calcolo; storage e altre componenti restano nei report Billing ufficiali. Gli importi mostrati sono stime, non fatture.</p><div class="settings-form"><label data-user-label ${admin?'':'hidden'}>Account<select data-user></select></label><label>Cadenza riepilogo<select data-cadence></select></label><label>Lingua email<select data-language disabled title="La lingua delle email segue la lingua del profilo utente"><option value="it">Italiano</option><option value="en">English</option></select></label><button data-save>Salva preferenze</button></div>${admin?'<div class="settings-form"><label>Cadenza predefinita del server<select data-default></select></label><button data-save-default>Salva predefinita</button></div>':''}<p data-status role="status" aria-live="polite"></p><div class="settings-form"><label>Da (UTC)<input data-start type="date"></label><label>Al (UTC, escluso)<input data-end type="date"></label><label>Token applicazione<select data-token><option value="">Tutti i token e job web</option></select></label><button data-refresh>Aggiorna report</button></div><div data-totals></div><div style="overflow:auto" tabindex="0" role="region" aria-label="Risorse contabilizzate"><table class="users-table"><thead><tr><th>Token / applicazione</th><th>Job</th><th>Risorse contabilizzate</th><th>Di cui consumi accettati</th><th>Dati non contabilizzati</th><th>Importo stimato</th><th>Crediti CPU/GPU utilizzati</th></tr></thead><tbody data-rows></tbody></table></div><details><summary>Le tue credenziali AI</summary><p>La revoca interrompe l’accesso dell’istanza; i consumi già registrati restano nei report.</p><div data-tokens></div></details>`;
const q=s=>root.querySelector('[data-'+s+']');for(const [value,label] of choices)q('cadence').add(new Option(label,value));if(admin)for(const [value,label] of choices.filter(x=>x[0]))q('default').add(new Option(label,value));
const now=new Date();q('end').value=new Date(now.getTime()+86400000).toISOString().slice(0,10);q('start').value=new Date(now.getTime()-30*86400000).toISOString().slice(0,10);
let preferencesSequence=0,reportSequence=0,preferenceNote='';
const endpoint=()=>admin?'/api/admin/ai-notifications?user_id='+q('user').value:'/api/account/ai-notifications';
const showError=e=>q('status').textContent=e.message;
async function preferences(){const serial=++preferencesSequence,d=await api(endpoint());if(serial!==preferencesSequence)return;q('cadence').value=d.cadence||'';q('language').value=d.language;preferenceNote=(d.smtp_configured?'SMTP configurato':'SMTP non configurato: email non inviate')+' · cadenza effettiva: '+d.effective_cadence;q('status').textContent=preferenceNote;}
async function report(){
 const serial=++reportSequence;
 q('rows').replaceChildren();q('totals').textContent=window.MtaLocale?.language==='it'?'Caricamento…':'Loading…';
 try{
  const uid=admin?q('user').value:null;if(admin&&!uid)return;
  const params=new URLSearchParams({start:String(Date.parse(q('start').value+'T00:00:00Z')/1000),end:String(Date.parse(q('end').value+'T00:00:00Z')/1000)});
  if(uid)params.set('user_id',uid);if(q('token').value)params.set('token_id',q('token').value);
  const d=await api((admin?'/api/admin':'/api/account')+'/ai-resources?'+params);if(serial!==reportSequence)return;
  q('status').textContent=preferenceNote;q('totals').textContent=d.jobs+' job · importo stimato € '+(d.amount_micro/1e6).toFixed(6)+' · billing '+(d.billing_enabled?'attivo':'disattivo');
  q('rows').replaceChildren();
  for(const row of d.by_token){
   const line=document.createElement('tr');
   for(const value of [(row.token_id??'Web')+' · '+row.label,row.jobs,fmt(row.usage),fmt(row.trusted_estimated_usage),fmt(row.diagnostic),'€ '+(row.amount_micro/1e6).toFixed(6),'€ '+((row.credits_debited_micro||0)/1e6).toFixed(6)]){const td=document.createElement('td');td.textContent=value;line.append(td)}
   q('rows').append(line);
  }
  if(!d.by_token.length){const row=document.createElement('tr'),cell=document.createElement('td');cell.colSpan=7;cell.textContent=window.MtaLocale?.language==='it'?'Nessuna riga nel periodo selezionato.':'No rows in the selected interval.';row.append(cell);q('rows').append(row);}
 }catch(e){
  if(serial!==reportSequence)return;q('rows').replaceChildren();q('totals').textContent='';
  const row=document.createElement('tr'),cell=document.createElement('td');cell.colSpan=7;cell.textContent=window.MtaLocale?.language==='it'?'Report non disponibile. Riprovare senza interpretare lo storico mancante come zero.':'Report unavailable. Retry; missing history is not zero.';
  row.append(cell);q('rows').append(row);throw e;
 }
}
async function tokens(){const values=await api(admin?'/api/admin/ai-tokens':'/api/account/ai-tokens');const uid=admin?Number(q('user').value):null;const rows=values.filter(t=>!admin||t.user_id===uid);const old=q('token').value;q('token').replaceChildren(new Option('Tutti i token e job web',''));q('tokens').replaceChildren();for(const token of rows){q('token').add(new Option('#'+token.id+' · '+token.label+(token.revoked_at?' (revocato)':''),token.id));const p=document.createElement('p');p.textContent='#'+token.id+' · '+token.label+' · '+(token.revoked_at?'revocato':'attivo');if(!admin&&!token.revoked_at){const b=document.createElement('button');b.textContent='Revoca';b.onclick=async()=>{if(!confirm('Revocare il token #'+token.id+'?'))return;try{await api('/api/account/ai-tokens/'+token.id,'DELETE');await tokens()}catch(e){showError(e)}};p.append(' ',b)}q('tokens').append(p)}q('token').value=old;}
q('save').onclick=async()=>{try{await api(admin?'/api/admin/ai-notifications':'/api/account/ai-notifications','PUT',{...(admin?{user_id:Number(q('user').value)}:{}),cadence:q('cadence').value||null,language:q('language').value});await preferences()}catch(e){showError(e)}};window.addEventListener('mta:language',()=>preferences().catch(showError));q('refresh').onclick=()=>report().catch(showError);q('token').onchange=()=>report().catch(showError);
(async()=>{if(admin){const [users,defaults]=await Promise.all([api('/api/admin/users'),api('/api/admin/ai-notifications')]);for(const user of users)q('user').add(new Option((user.display_name||user.username)+' (#'+user.id+')',user.id));q('default').value=defaults.default_cadence;q('save-default').onclick=async()=>{try{await api('/api/admin/ai-notifications','PUT',{cadence:q('default').value});await preferences()}catch(e){showError(e)}};q('user').onchange=async()=>{try{await preferences();await tokens();await report()}catch(e){showError(e)}};}await preferences();await tokens();await report()})().catch(showError);
}
for(const root of document.querySelectorAll('.ai-resource-panel'))mount(root);
})();
