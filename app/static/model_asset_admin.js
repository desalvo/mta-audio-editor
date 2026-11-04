/* Engine-grouped admin maintenance: no user-supplied URL or server path. */
(()=>{'use strict';
const host=document.querySelector('[data-model-assets]');if(!host)return;
const T=(it,en)=>document.documentElement.lang.startsWith('en')?en:it;
const E=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let page=0,epoch=0,rows=new Map();
const status=host.querySelector('[data-model-status]'),files=host.querySelector('[data-model-files]');
const mega=document.createElement('section');mega.className='settings-form';mega.innerHTML=`<h3>Mega 53 · checkpoint</h3><p>${T('1. Verifica i diritti e scarica il checkpoint originale v1.0.21 dalla fonte. 2. Caricalo esplicitamente: il server verifica lo SHA-256 prima di sostituire il file. 3. Verifica la configurazione sul worker che esegue la separazione.','1. Review the rights and obtain the original v1.0.21 checkpoint from its source. 2. Upload it explicitly: the server verifies SHA-256 before replacing the file. 3. Verify configuration on the worker that executes separation.')}</p><a href="https://github.com/ZFTurbo/Music-Source-Separation-Training/releases/tag/v1.0.21" target="_blank" rel="noopener noreferrer">${T('Release originale','Original release')}</a><label>${T('Checkpoint originale','Original checkpoint')} <input type="file" data-mega-file></label><button type="button" data-mega-install>${T('Installa checkpoint','Install checkpoint')}</button> <button type="button" data-mega-verify>${T('Verifica checkpoint','Verify checkpoint')}</button><p>${T('Il caricamento del solo checkpoint non installa il runtime; la procedura guidata installa sul nodo locale, non sui worker remoti.','Uploading only the checkpoint does not install the runtime; guided installation is local and does not configure remote workers.')}</p><p data-mega-status role="status" aria-live="polite"></p>`;host.insertBefore(mega,host.querySelector('details'));
const request=async(url,options={})=>{const response=await fetch(url,{...options,headers:{'X-MTA-Request':'1',...(options.headers||{})}});if(!response.ok){let error;try{error=(await response.json()).detail}catch{error=response.statusText}throw new Error(error||String(response.status))}return response.json()};
const json=body=>({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
mega.insertAdjacentHTML('afterbegin',`<h3>${T('Installazione guidata Mega 53','Guided Mega 53 installation')}</h3><p>${T('Installa codice, dipendenze, YAML e checkpoint verificati sul nodo locale. Il download supera 1,3 GB. Richiede Git, spazio libero e un runtime Python di base; un worker remoto deve installare separatamente.','Installs verified code, dependencies, YAML and checkpoint on the local node. The download exceeds 1.3 GB. Git, free disk space and a base Python runtime are required; a remote worker must be installed separately.')}</p><label>${T('Acceleratore','Accelerator')} <select data-mega-device><option value="auto">Auto</option><option value="cpu">CPU</option><option value="cuda">CUDA</option><option value="rocm">ROCm</option></select></label> <button type="button" data-mega-runtime>${T('Installa Mega 53','Install Mega 53')}</button>`);
const bytes=value=>value==null?'—':fmtBytes(value);
function accepted(value){const id=value.job_id||(value.status&&value.kind?value.id:null);if(id&&/^[A-Za-z0-9_-]{1,160}$/.test(id)){window.dispatchEvent(new CustomEvent('mta:ai-job-accepted',{detail:{job_id:id,origin:host}}));status.textContent=T('Download accettato nella coda AI: ','Download accepted in the AI queue: ')+id;return id}return null}
const dialog=document.createElement('dialog');
dialog.className='settings-card model-operation-dialog';
dialog.setAttribute('aria-labelledby','modelOperationTitle');
dialog.innerHTML=`<h2 id="modelOperationTitle"></h2><progress max="100" aria-labelledby="modelOperationTitle"></progress><p role="status"></p><form method="dialog"><button>${T('Chiudi','Close')}</button></form>`;
host.append(dialog);
const progressBar=dialog.querySelector('progress'), progressText=dialog.querySelector('[role="status"]');
let operationRunning=false;
function progress(message,value=null){
  progressText.textContent=message+(value!=null&&value>=0?' · '+Number(value).toFixed(0)+'%':'');
  if(value==null||value<0)progressBar.removeAttribute('value');else progressBar.value=value;
}
async function operation(title,run){
  if(operationRunning)throw new Error(T('Attendi l’operazione in corso','Wait for the current operation'));
  operationRunning=true;
  dialog.querySelector('h2').textContent=title;
  progress(T('Preparazione…','Preparing…'));
  if(!dialog.open)dialog.showModal();
  try{
    await run();
    progress(T('Operazione completata','Operation completed'),100);
    await load();
  }catch(error){
    progress(error.message,0);
    status.textContent=error.message;
  }finally{operationRunning=false}
}
window.mtaModelAssetOperation=operation;
async function watch(id,kind='file'){
  const url=kind==='media'?'/api/media-jobs/'+id:kind==='studio'?'/api/admin/ai/studio/installations/'+id:kind==='mega'?'/api/admin/ai/mega53/runtime/installations/'+id:'/api/admin/ai/model-assets/jobs/'+id;
  while(host.isConnected){
    const job=await request(url),state=job.state||job.status;
    progress(job.message||job.phase||state,job.progress_percent??job.progress);
    if(state==='completed')return;
    if(!['queued','running','blocked'].includes(state))throw new Error(job.error||job.message||state);
    await new Promise(resolve=>setTimeout(resolve,1000));
  }
}
async function startOperation(url,options,kind){
  const result=await request(url,options),id=accepted(result);
  if(id)await watch(id,kind);
}
function runtimeCard(runtime){
  const hostRuntime=host.querySelector('[data-ai-runtimes]');
  if(!runtime||!hostRuntime)return;
  const summary=runtime.managed?T('Installato da MTA','Managed installation'):runtime.disabled?T('Disinstallato','Uninstalled'):T('Configurazione del sistema','System configuration');
  hostRuntime.innerHTML=`<article class="settings-form"><b>${T('Runtime audio condiviso','Shared audio runtime')} · ${summary}</b><small>${E(runtime.engines.join(', '))}</small>
    <small>${T('I pesi dei modelli sono gestiti separatamente. I runtime esterni e i worker remoti si gestiscono sul nodo di esecuzione.','Model weights are managed separately. External runtimes and remote workers are managed on their execution node.')}</small>
    ${runtime.can_install&&!runtime.managed?`<label>${T('Acceleratore','Accelerator')} <select data-audio-device><option value="auto">Auto</option><option value="cpu">CPU</option><option value="cuda">CUDA</option><option value="rocm">ROCm</option></select></label><button type="button" data-runtime-install>${T('Installa motori audio','Install audio engines')}</button>`:''}
    ${runtime.can_remove?`<button type="button" class="danger" data-runtime-remove>${runtime.managed?T('Disinstalla motori audio','Uninstall audio engines'):T('Disattiva runtime di sistema','Disable system runtime')}</button>`:''}
    </article>`;
}
function matches(row){return !host.querySelector('[data-model-engine]').value||row.engine===host.querySelector('[data-model-engine]').value}
async function load(){const ticket=++epoch;status.textContent=T('Lettura inventario…','Reading inventory…');try{const engine=host.querySelector('[data-model-engine]').value,search=host.querySelector('[data-model-search]').value;const data=await request('/api/admin/ai/model-assets?'+new URLSearchParams({engine,search,offset:String(page),limit:'100'}));if(ticket!==epoch)return;rows=new Map(data.files.map(row=>[row.id,row]));const select=host.querySelector('[data-model-engine]');select.innerHTML='<option value="">'+T('Tutti i motori','All engines')+'</option>'+data.engines.map(item=>`<option value="${E(item.id)}">${E(item.name)} (${item.files})</option>`).join('');select.value=engine;
files.innerHTML=data.files.map(row=>`<tr data-file="${row.id}"><td>${E(row.engines.join(', '))}<br><small>${E(row.asset_id||row.origin)}</small></td><td><code>${E(row.name)}</code>${row.expected_sha256?`<details><summary>SHA-256</summary><code>${E(row.expected_sha256)}</code></details>`:''}${row.source?.role?`<br><small>${E(row.source.role)}</small>`:''}${row.source?`<br><a href="${E(row.source.source_url)}" target="_blank" rel="noopener noreferrer">${T('Fonte e licenza','Source and license')}</a>`:''}</td><td>${row.installed?T('Presente','Present'):T('Mancante','Missing')}<br>${bytes(row.bytes)}</td><td>${row.can_download?`<button data-download="${row.id}">${T('Scarica dalla fonte','Download from source')}</button>`:''}${row.installed?`<a class="admin-download" href="/api/admin/ai/model-assets/${row.id}/file">${T('Esporta file','Export file')}</a> <button class="danger" data-remove="${row.id}">${T('Elimina file','Delete file')}</button>`:''}${row.can_restore?`<button data-restore="${row.id}">${T('Ripristina file esatto','Restore exact file')}</button>`:''}${!row.can_download&&!row.can_restore?`<small>${T('Installare il pacchetto autorizzato completo o usare la ricetta del motore.','Install the complete authorized bundle or use the engine recipe.')}</small>`:''}</td></tr>`).join('')||`<tr><td colspan="4">${T('Nessun file nel filtro selezionato','No files in the selected filter')}</td></tr>`;
host.querySelector('[data-model-page]').textContent=data.total?`${page+1}–${Math.min(page+100,data.total)} / ${data.total}`:'0 / 0';host.querySelector('[data-model-prev]').disabled=page===0;host.querySelector('[data-model-next]').disabled=data.next_offset==null;
host.querySelector('[data-model-recipes]').innerHTML=data.recipes.filter(matches).map(row=>`<article class="settings-form" data-recipe="${E(row.id)}"><b>${E(row.engine)} · ${E(row.name)}</b>${row.note?`<small>${E(row.note)}</small>`:''}<div>${row.install_url?`<button data-recipe-install="${E(row.id)}">${T('Scarica / installa','Download / install')}</button>`:''}${(row.delete_url||row.remove_job_url)?`<button class="danger" data-recipe-delete="${E(row.id)}">${T('Rimuovi modello completo','Remove complete model')}</button>`:''}</div></article>`).join('');host._recipes=new Map(data.recipes.map(row=>[row.id,row]));runtimeCard(data.runtime);status.textContent=data.complete?T('Inventario completo delle radici configurate. I download non concedono diritti né attivano modelli.','Complete inventory of configured roots. Downloads do not grant rights or activate models.'):T('Inventario con avvisi: ','Inventory warnings: ')+data.warnings.join('; ');
}catch(error){if(ticket===epoch)status.textContent=error.message}}
function consent(){if(!host.querySelector('[data-model-consent]').checked)throw new Error(T('Verificare prima le licenze esatte delle componenti.','Review the exact component licenses first.'))}
mega.querySelector('[data-mega-runtime]').onclick=async()=>{
  try{
    consent();
    await operation(T('Installazione runtime Mega 53','Installing Mega 53 runtime'),()=>startOperation(
      '/api/admin/ai/mega53/runtime/install',json({accept_licenses:true,device:mega.querySelector('[data-mega-device]').value}),'mega'));
  }catch(error){mega.querySelector('[data-mega-status]').textContent=error.message}
};
function megaResult(result){return T('Checkpoint verificato. ','Checkpoint verified. ')+(result.paths_ready?T('Percorsi locali presenti; inferenza non ancora verificata.','Local paths present; inference not yet tested.'):T('Runtime o configurazione non disponibili su questo server; completare la configurazione del worker.','Runtime or configuration unavailable on this server; complete worker setup.'))}
mega.querySelector('[data-mega-install]').onclick=async()=>{const message=mega.querySelector('[data-mega-status]');try{consent();const file=mega.querySelector('[data-mega-file]').files[0];if(!file)throw new Error(T('Selezionare il checkpoint.','Select a checkpoint.'));message.textContent=T('Caricamento e verifica in corso…','Uploading and verifying…');message.textContent=megaResult(await request('/api/admin/ai/mega53/checkpoint/install?accept_licenses=true',{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:file}))}catch(error){message.textContent=error.message}};
mega.querySelector('[data-mega-verify]').onclick=async()=>{const message=mega.querySelector('[data-mega-status]');try{message.textContent=T('Verifica in corso…','Verifying…');message.textContent=megaResult(await request('/api/admin/ai/mega53/checkpoint/verify',json({})))}catch(error){message.textContent=error.message}};
host.addEventListener('click',async event=>{
  const button=event.target.closest('button');if(!button)return;
  let action='';
  for(const key of ['download','remove','restore','recipeInstall','recipeDelete','runtimeInstall','runtimeRemove'])
    if(Object.hasOwn(button.dataset,key))action=key;
  if(!action)return;
  button.disabled=true;
  const identifier=button.dataset[action];
  const removing=['remove','recipeDelete','runtimeRemove'].includes(action);
  const title=removing?T('Disinstallazione in corso','Uninstalling'):T('Download e installazione','Downloading and installing');
  try{
    if(action==='restore'){
      const input=host.querySelector('[data-model-restore]');input.dataset.id=identifier;input.value='';input.click();return;
    }
    if(removing){
      if(!confirm(T('Confermi la rimozione?','Confirm removal?')))return;
    }else consent();
    const base='/api/admin/ai/model-assets/';
    const recipe=host._recipes?.get(identifier);
    await operation(title,async()=>{
      if(action==='runtimeInstall')await startOperation(base+'runtime/install',json({
        accept_licenses:true,device:host.querySelector('[data-audio-device]').value}));
      else if(action==='runtimeRemove')await startOperation(base+'runtime/remove',json({}));
      else if(action==='download')await startOperation(base+identifier+'/download',json({accept_licenses:true}));
      else if(action==='remove')await request(base+identifier,{method:'DELETE'});
      else if(action==='recipeInstall')await startOperation(recipe.install_url,json(recipe.body||{}),
        recipe.install_url.includes('/download-jobs')?'media':recipe.install_url.includes('/mega53/weights/')?'file':recipe.install_url.includes('/mega53/')?'mega':'studio');
      else if(recipe.remove_job_url)await startOperation(recipe.remove_job_url,json({}));
      else await request(recipe.delete_url,{method:'DELETE'});
    });
  }catch(error){status.textContent=error.message}finally{button.disabled=false}
});
host.querySelector('[data-model-restore]').addEventListener('change',async event=>{const input=event.target,file=input.files[0];if(!file)return;try{consent();status.textContent=T('Verifica e ripristino del file…','Verifying and restoring file…');await request('/api/admin/ai/model-assets/'+input.dataset.id+'/restore',{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:file});await load()}catch(error){status.textContent=error.message}});
host.querySelector('[data-model-upload]').addEventListener('change',async event=>{
  const file=event.target.files[0];if(!file)return;
  try{
    consent();
    await operation(T('Installazione pacchetto modello','Installing model bundle'),()=>startOperation(
      '/api/admin/ai/studio/assets/install?accept_licenses=true',
      {method:'POST',headers:{'Content-Type':'application/zip'},body:file},'studio'));
  }catch(error){status.textContent=error.message}
  finally{event.target.value=''}
});
host.querySelector('[data-model-reload]').onclick=()=>load();host.querySelector('[data-model-engine]').onchange=()=>{page=0;void load()};let searchTimer;host.querySelector('[data-model-search]').oninput=()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>{page=0;void load()},300)};host.querySelector('[data-model-prev]').onclick=()=>{page=Math.max(0,page-100);void load()};host.querySelector('[data-model-next]').onclick=()=>{page+=100;void load()};document.querySelector('[data-tab="models"]')?.addEventListener('click',()=>load());if(location.hash==='#models')void load();
})();
