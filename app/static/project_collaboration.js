/* Shared project discussion and guarded live snapshots. No project authority is
 * held in this client: membership, revisions, media expiry and mail are server
 * decisions. Local conflicts remain recoverable until explicitly discarded. */
(function(global){
 'use strict';
 const state={project:null,user:null,callbacks:{},source:null,open:false,minimized:false,messages:new Map(),cursor:0,status:null,pending:null,settleTimer:null,settleBlocked:false,loading:false,recording:null,stream:null};
 const byId=id=>document.getElementById(id);
 const escape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const isShared=(project,user)=>!!project?.id&&Number(user?.id)>0&&!user?.native_single_user&&(project.shared_with_user_ids||[]).length>0&&(Number(user.id)===project.owner_user_id||(project.shared_with_user_ids||[]).includes(Number(user.id)));
 async function request(path,options={}){
  const headers={'X-MTA-Request':'1',...(options.headers||{})};
  const response=await fetch(path,{credentials:'same-origin',...options,headers});
  if(!response.ok){let detail;try{detail=(await response.json()).detail}catch(_){}throw new Error(typeof detail==='string'?detail:'Collaborazione non disponibile ('+response.status+')')}
  return response.status===204?null:response.json();
 }
 const url=suffix=>'/api/projects/'+encodeURIComponent(state.project.id)+'/collaboration'+suffix;
 function notify(message){if(state.callbacks.toast)state.callbacks.toast(message);else if(byId('mtaCollaborationStatus'))byId('mtaCollaborationStatus').textContent=message}
 function cancelSettlement(){if(state.settleTimer!==null)clearTimeout(state.settleTimer);state.settleTimer=null}
 function disconnect(){cancelSettlement();state.source?.close();state.source=null;stopRecording(true)}
 function normalizePending(){
  const pending=state.pending;
  if(pending&&(!state.project||pending.id!==state.project.id||Number(pending.collaboration_revision)<=Number(state.project.collaboration_revision||0)))state.pending=null;
  if(!state.pending){state.settleBlocked=false;cancelSettlement()}
 }
 function queueSettlement(){
  normalizePending();
  if(!state.pending||state.settleBlocked)return;
  const busy=!!state.callbacks.isBusy?.();
  if(!busy&&state.callbacks.isDirty?.()){cancelSettlement();return}
  if(state.settleTimer===null)state.settleTimer=setTimeout(settlePending,busy?100:0);
 }
 function settlePending(){
  cancelSettlement();normalizePending();
  if(!state.pending)return;
  if(state.callbacks.isBusy?.()){queueSettlement();return}
  if(state.callbacks.isDirty?.())return;
  const project=state.pending;
  try{
   if(!state.callbacks.applyRemote||state.callbacks.applyRemote(project)===false){
    // A refused clean callback must not spin. A later sync/saved event retries;
    // only an actually busy editor needs the short settlement timer.
    if(state.callbacks.isBusy?.())queueSettlement();else state.settleBlocked=true;
    return;
   }
   if(state.project?.id===project.id&&Number(state.project.collaboration_revision||0)<=Number(project.collaboration_revision))state.project=project;
   normalizePending();renderConflict();
  }catch(error){state.settleBlocked=true;notify(error.message)}
 }
 function sync(project,user,callbacks){
  if(callbacks)state.callbacks=callbacks;
  const previous=state.project?.id;state.project=project;state.user=user;
  state.settleBlocked=false;normalizePending();
  if(!isShared(project,user)){
   disconnect();state.open=false;state.pending=null;state.status=null;state.messages.clear();state.cursor=0;
   byId('mtaCollaborationNav')?.remove();byId('mtaCollaborationWindow')?.remove();return;
  }
  if(previous!==project.id){disconnect();state.messages.clear();state.cursor=0;state.open=false;state.pending=null;state.status=null;byId('mtaCollaborationWindow')?.remove()}
  mountNav();
  if(!state.source){
   state.source=new EventSource(url('/events'));
   state.source.addEventListener('collaboration',event=>receive(JSON.parse(event.data)));
   state.source.addEventListener('revoked',()=>{notify('La condivisione è terminata o è stata revocata. Le modifiche locali non salvate restano disponibili.');disconnect();byId('mtaCollaborationNav')?.remove();byId('mtaCollaborationWindow')?.remove();state.callbacks.revoked?.()});
   state.source.onerror=()=>{if(byId('mtaCollaborationStatus'))byId('mtaCollaborationStatus').textContent='Connessione in ripristino…'};
  }
  renderBadge();
  queueSettlement();
 }
 function mountNav(){
  if(byId('mtaCollaborationNav'))return;
  const nav=document.querySelector('.sidebar nav');if(!nav)return;
  const button=document.createElement('button');button.id='mtaCollaborationNav';button.className='nav-item collaboration-nav';button.type='button';
  button.innerHTML='☏ <span>Dashboard condivisa</span> <b id="mtaCollaborationBadge" class="collaboration-unread" hidden></b>';
  button.addEventListener('click',open);nav.prepend(button);
 }
 function renderBadge(){const badge=byId('mtaCollaborationBadge');if(badge){const count=Number(state.status?.unread||0);badge.textContent=String(count);badge.hidden=!count;badge.setAttribute('aria-label',count+' messaggi non letti')}}
 async function receive(status){
  if(status.project_id!==state.project?.id)return;
  state.status=status;
  for(const message of status.messages||[]){state.messages.set(message.id,message);state.cursor=Math.max(state.cursor,message.id)}
  renderBadge();
  const remote=status.project;
  if(remote&&Number(remote.collaboration_revision)>Number(state.project.collaboration_revision||0)){
   state.pending=remote;state.settleBlocked=false;
   if(!state.callbacks.isDirty?.()&&!state.callbacks.isBusy?.())settlePending();
  }
  queueSettlement();
  renderMessages();renderConflict();
  if(status.latest_message_id>state.cursor&&!state.loading)await loadMessages();
  if(state.open&&!state.minimized)await readAll();
 }
 async function loadMessages(){
  if(state.loading||!state.project)return;state.loading=true;
  const pid=state.project.id;
  try{
   let more=true;
   while(more&&state.project?.id===pid){
    const status=await request(url('?after='+state.cursor));
    if(!status.shared){disconnect();byId('mtaCollaborationNav')?.remove();byId('mtaCollaborationWindow')?.remove();return}
    state.status={...state.status,...status};
    for(const message of status.messages){state.messages.set(message.id,message);state.cursor=Math.max(state.cursor,message.id)}
    more=status.has_more;
   }
   renderMessages();renderBadge();
  }catch(error){notify(error.message)}finally{state.loading=false}
 }
 function mountWindow(){
  if(byId('mtaCollaborationWindow'))return;
  const panel=document.createElement('section');panel.id='mtaCollaborationWindow';panel.className='collaboration-window';panel.setAttribute('role','dialog');panel.setAttribute('aria-label','Dashboard condivisa');
  panel.innerHTML='<header class="collaboration-title"><strong id="mtaCollaborationTitle"></strong><div><button type="button" data-action="minimize" aria-label="Iconizza o ripristina dashboard">_</button><button type="button" data-action="close" aria-label="Chiudi dashboard">×</button></div></header><div class="collaboration-body"><div id="mtaCollaborationConflict" class="collaboration-conflict" hidden></div><div id="mtaCollaborationMembers" class="hint"></div><div id="mtaCollaborationMessages" class="collaboration-messages" aria-live="polite"></div><form id="mtaCollaborationForm"><label>Messaggio<textarea id="mtaCollaborationText" maxlength="20000" rows="3"></textarea></label><div class="collaboration-actions"><button type="submit">Invia</button><label class="collaboration-attachment">Immagine / audio<input id="mtaCollaborationFile" type="file" accept="image/png,image/jpeg,image/gif,image/webp,audio/*"></label><button type="button" data-action="record" id="mtaCollaborationRecord">Registra voce</button><button type="button" data-action="leave" id="mtaCollaborationLeave">Abbandona condivisione</button></div></form><p id="mtaCollaborationStatus" role="status"></p></div>';
  document.body.append(panel);
  panel.querySelector('[data-action="close"]').addEventListener('click',close);
  panel.querySelector('[data-action="minimize"]').addEventListener('click',()=>{state.minimized=!state.minimized;panel.classList.toggle('minimized',state.minimized);if(!state.minimized)void readAll()});
  panel.querySelector('[data-action="leave"]').addEventListener('click',leave);
  panel.querySelector('[data-action="record"]').addEventListener('click',record);
  byId('mtaCollaborationForm').addEventListener('submit',sendText);
  byId('mtaCollaborationFile').addEventListener('change',event=>{const file=event.target.files?.[0];if(file)void sendFile(file);event.target.value=''});
  makeDraggable(panel,panel.querySelector('.collaboration-title'));
 }
 function makeDraggable(panel,handle){
  let drag=null;
  handle.addEventListener('pointerdown',event=>{if(event.target.closest('button'))return;const rect=panel.getBoundingClientRect();drag={x:event.clientX-rect.left,y:event.clientY-rect.top};handle.setPointerCapture(event.pointerId);event.preventDefault()});
  handle.addEventListener('pointermove',event=>{if(!drag)return;panel.style.left=Math.max(0,Math.min(window.innerWidth-100,event.clientX-drag.x))+'px';panel.style.top=Math.max(0,Math.min(window.innerHeight-40,event.clientY-drag.y))+'px';panel.style.right='auto';panel.style.bottom='auto'});
  const end=()=>{drag=null};handle.addEventListener('pointerup',end);handle.addEventListener('pointercancel',end);
 }
 async function open(){
  if(!isShared(state.project,state.user))return;
  state.open=true;state.minimized=false;mountWindow();const panel=byId('mtaCollaborationWindow');panel.hidden=false;panel.classList.remove('minimized');
  renderMessages();renderConflict();await loadMessages();await readAll();
 }
 function close(){state.open=false;stopRecording(true);const panel=byId('mtaCollaborationWindow');if(panel)panel.hidden=true;renderBadge()}
 function renderMessages(){
  if(!byId('mtaCollaborationWindow'))return;
  byId('mtaCollaborationTitle').textContent=state.status?.title||state.project.title;
  byId('mtaCollaborationMembers').textContent=(state.status?.participants||[]).map(user=>user.name+(user.owner?' (owner)':'')).join(' · ');
  byId('mtaCollaborationLeave').hidden=state.project.owner_user_id===Number(state.user.id);
  const container=byId('mtaCollaborationMessages'),bottom=container.scrollHeight-container.scrollTop-container.clientHeight<80;
  container.innerHTML=[...state.messages.values()].sort((a,b)=>a.id-b.id).map(message=>{
   const color=/^hsl\([0-9.]+ 66% 56%\)$/.test(message.color)?message.color:'currentColor';
   let media='';
   if(message.media_id){
    if(message.expired)media='<small>Allegato scaduto e rimosso dal server</small>';
    else if(message.media_url&&message.media_url.startsWith('/api/projects/'))media=message.media_type?.startsWith('image/')?'<a href="'+escape(message.media_url)+'" target="_blank" rel="noopener"><img src="'+escape(message.media_url)+'" alt="Immagine condivisa" loading="lazy"></a>':'<audio src="'+escape(message.media_url)+'" controls preload="none"></audio>';
   }
   return '<article class="collaboration-message" data-message-id="'+Number(message.id)+'"><b style="color:'+color+'">'+escape(message.sender)+'</b> <time>'+escape(new Date(message.created_at*1000).toLocaleString())+'</time><div class="collaboration-message-text">'+escape(message.text)+'</div>'+media+'</article>';
  }).join('');
  if(bottom)container.scrollTop=container.scrollHeight;
 }
 async function readAll(){
  if(!state.open||state.minimized||!state.status?.latest_message_id)return;
  try{await request(url('/read'),{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({message_id:state.status.latest_message_id})});state.status.unread=0;renderBadge()}catch(error){notify(error.message)}
 }
 async function sendText(event){
  event.preventDefault();const input=byId('mtaCollaborationText'),text=input.value.trim();if(!text)return;
  try{const message=await request(url('/messages'),{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({text})});input.value='';state.messages.set(message.id,message);renderMessages();notify('Messaggio inviato. Le notifiche email sono accodate se SMTP è configurato.')}catch(error){notify(error.message)}
 }
 async function sendFile(file){
  if(file.size>20*1024*1024)return notify('Allegato troppo grande (massimo 20 MiB)');
  const body=new FormData();body.append('file',file,file.name||'voice.webm');
  try{notify('Invio allegato…');const message=await request(url('/media'),{method:'POST',body});state.messages.set(message.id,message);renderMessages();notify('Allegato inviato · scadenza '+(state.status?.attachment_ttl_hours||24)+' ore')}catch(error){notify(error.message)}
 }
 async function record(){
  if(state.recording){stopRecording(false);return}
  if(!global.MediaRecorder||!navigator.mediaDevices?.getUserMedia)return notify('Registrazione vocale non disponibile in questo browser o contesto sicuro');
  try{
   const pid=state.project?.id,stream=await navigator.mediaDevices.getUserMedia({audio:true});
   if(!state.open||state.project?.id!==pid){stream.getTracks().forEach(track=>track.stop());return}
   state.stream=stream;
   const recorder=new MediaRecorder(stream),chunks=[];let bytes=0;state.recording=recorder;
   const timer=setTimeout(()=>stopRecording(false),30*60*1000);
   recorder.addEventListener('dataavailable',event=>{if(event.data.size){chunks.push(event.data);bytes+=event.data.size;if(bytes>19*1024*1024&&recorder.state!=='inactive')stopRecording(false)}});
   recorder.addEventListener('stop',()=>{clearTimeout(timer);stream.getTracks().forEach(track=>track.stop());state.stream=null;state.recording=null;byId('mtaCollaborationRecord')&&(byId('mtaCollaborationRecord').textContent='Registra voce');if(!recorder.cancelled&&chunks.length&&state.project?.id===pid)void sendFile(new File(chunks,'voice.webm',{type:recorder.mimeType||'audio/webm'}))});
   recorder.start(1000);byId('mtaCollaborationRecord').textContent='Interrompi e invia';notify('Registrazione in corso…');
  }catch(error){stopRecording(true);notify(error.message)}
 }
 function stopRecording(cancel){
  if(state.recording){state.recording.cancelled=!!cancel;if(state.recording.state!=='inactive')state.recording.stop()}
  state.stream?.getTracks().forEach(track=>track.stop());
 }
 async function leave(){
  if(!global.confirm('Abbandonare la condivisione? I messaggi restano agli altri partecipanti.'))return;
  try{await request(url('/leave'),{method:'POST'});disconnect();byId('mtaCollaborationNav')?.remove();byId('mtaCollaborationWindow')?.remove();state.callbacks.left?.()}catch(error){notify(error.message)}
 }
 function renderConflict(){
  const box=byId('mtaCollaborationConflict');if(!box)return;box.hidden=!state.pending;if(!state.pending)return;
  const owner=state.project.owner_user_id===Number(state.user.id);
  box.innerHTML='<b>Il progetto condiviso è cambiato.</b><p>'+ (owner?'Le tue modifiche hanno priorità quando salvi.':'Le modifiche locali sono conservate e non sovrascriveranno la nuova versione.')+'</p><button type="button" data-conflict="copy">Scarica copia locale delle modifiche</button> <button type="button" data-conflict="reload">Carica versione condivisa</button>';
  box.querySelector('[data-conflict="copy"]').addEventListener('click',downloadLocalCopy);
  box.querySelector('[data-conflict="reload"]').addEventListener('click',()=>{if(global.confirm('Sostituire le modifiche locali con la versione condivisa? Scarica prima una copia se vuoi conservarle.'))applyPending()});
 }
 function downloadLocalCopy(){
  if(state.callbacks.downloadLocalCopy)return state.callbacks.downloadLocalCopy();
  const blob=new Blob([JSON.stringify(state.project,null,2)],{type:'application/json'}),objectUrl=URL.createObjectURL(blob),link=document.createElement('a');
  link.href=objectUrl;link.download=(state.project.title||'project')+'-local-conflict.maeproj';link.click();setTimeout(()=>URL.revokeObjectURL(objectUrl),1000);
 }
 function applyPending(){
  if(!state.pending||!state.callbacks.applyRemote)return;
  const project=state.pending;
  try{
   // Only this explicit confirmation may replace dirty local state.
   if(state.callbacks.applyRemote(project,true)===false)return;
   state.pending=null;state.project=project;renderConflict();
  }catch(error){notify(error.message)}
 }
 function beforeSave(project){
  if(state.pending&&project.owner_user_id!==Number(state.user?.id)){
   notify('Conflitto nel progetto condiviso: apri la dashboard per conservare le modifiche locali e caricare la versione aggiornata.');
   throw new Error('PROJECT_COLLABORATION_CONFLICT');
  }
 }
 const missing=Symbol('missing');
 function same(a,b){
  if(a===b)return true;
  if(!a||!b||typeof a!=='object'||typeof b!=='object'||Array.isArray(a)!==Array.isArray(b))return false;
  const ak=Object.keys(a),bk=Object.keys(b);return ak.length===bk.length&&ak.every(key=>Object.prototype.hasOwnProperty.call(b,key)&&same(a[key],b[key]));
 }
 const clone=value=>value===missing?missing:JSON.parse(JSON.stringify(value));
 function mergeSnapshots(base,server,local){
  if(same(local,base))return clone(server);
  if(same(server,base)||same(server,local))return clone(local);
  const object=value=>value&&typeof value==='object'&&!Array.isArray(value);
  if(object(base)&&object(server)&&object(local)){
   const result=Object.create(null);
   for(const key of new Set([...Object.keys(base),...Object.keys(server),...Object.keys(local)])){
    const get=value=>Object.prototype.hasOwnProperty.call(value,key)?value[key]:missing;
    const value=mergeSnapshots(get(base),get(server),get(local));if(value!==missing)result[key]=value;
   }
   return result;
  }
  if([base,server,local].every(Array.isArray)&&[base,server,local].every(list=>list.every(item=>object(item)&&typeof item.id==='string'))){
   const maps=[base,server,local].map(list=>new Map(list.map(item=>[item.id,item])));
   if([base,server,local].every((list,i)=>list.length===maps[i].size)){
    const values=new Map();
    for(const id of new Set(maps.flatMap(map=>[...map.keys()]))){const value=mergeSnapshots(...maps.map(map=>map.has(id)?map.get(id):missing));if(value!==missing)values.set(id,value)}
    const ids=[base,server,local].map(list=>list.map(item=>item.id)),order=same(ids[0],ids[2])?ids[1]:ids[2];
    return [...new Set([...order,...ids[1],...ids[2]])].filter(id=>values.has(id)).map(id=>values.get(id));
   }
  }
  return clone(local);
 }
 function mergeSaved(sent,current,saved){
  const result=mergeSnapshots(sent,saved,current);
  for(const field of ['id','owner_user_id','shared_with_user_ids','collaboration_revision','ai_publication_token','archived_tracks','project_kind_version','audio_storage_mode']){
   if(Object.prototype.hasOwnProperty.call(saved,field))result[field]=clone(saved[field]);
  }
  return result;
 }
 function saved(project){
  if(state.project?.id!==project?.id)return;state.project=project;
  state.settleBlocked=false;normalizePending();renderConflict();queueSettlement();
 }
 async function conflict(){
  notify('Conflitto nel progetto condiviso: le modifiche locali restano disponibili nella dashboard.');
  if(!state.project)return;
  const pid=state.project.id;
  try{const remote=await request('/api/projects/'+encodeURIComponent(pid));if(state.project?.id===pid)state.pending=remote}catch(error){notify(error.message)}
  await open();renderConflict();
 }
 async function adminSettings(){
  const settings=await request('/api/admin/collaboration');const input=global.prompt('Durata immagini/audio dashboard in ore (1–720)',String(settings.attachment_ttl_hours));if(input===null)return;
  const hours=Number(input);if(!Number.isFinite(hours)||hours<1||hours>720)return notify('Durata non valida');
  await request('/api/admin/collaboration',{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify({attachment_ttl_hours:hours})});notify('Durata dei nuovi allegati aggiornata');
 }
 global.MtaCollaboration={sync,open,close,beforeSave,saved,conflict,adminSettings,downloadLocalCopy,mergeSaved};
})(window);
