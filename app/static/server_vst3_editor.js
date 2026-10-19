/* Original Linux plugin UI, rendered by its owning isolated server worker. */
(()=>{'use strict';
const nativeEditor=window.openOriginalVst3Editor;
let active=null;
const request=async(url,body)=>{const r=await fetch(url,{method:body===undefined?'GET':'POST',headers:{'Content-Type':'application/json','X-MTA-Request':'1'},body:body===undefined?undefined:JSON.stringify(body),cache:'no-store'});if(!r.ok){let e;try{e=(await r.json()).detail}catch{}const error=Error(e||r.statusText);error.status=r.status;throw error}return r};
window.openOriginalVst3Editor=async function(id,trackId){
 if(currentUser?.native_single_user)return nativeEditor(id,trackId);
 if(active)return active.element.focus();
 const pid=current?.id;if(!pid)return;
 let owned=false,sid=null,base=null,closed=false,closing=false,timer=null,queue=[],sending=false;
 const element=document.createElement('div');element.className='remote-vst-backdrop';element.innerHTML=`<section class="remote-vst-window" role="dialog" aria-modal="true" aria-label="${tr('Original plugin editor','Editor originale del plugin')}"><header><strong>${tr('Original plugin editor','Editor originale del plugin')}</strong><button class="utility-btn" data-close>${tr('Save and close','Salva e chiudi')}</button></header><p role="status">${tr('Preparing private plugin display…','Preparazione del display privato del plugin…')}</p><div class="remote-vst-viewport"><canvas tabindex="0"></canvas></div></section>`;
 document.body.appendChild(element);active={element};const canvas=element.querySelector('canvas'),status=element.querySelector('[role=status]');
 async function close(){
  if(closed||closing)return;closing=true;clearTimeout(timer);
  try{
   queue=[];if(base){await request(base+'/input',{events:[{type:'release'}]});const r=await(await request(base+'/state',{close:true})).json();if(r.state!=='completed')throw Error(tr('Plugin is still closing. Retry in a moment.','Il plugin si sta ancora chiudendo. Riprovare tra poco.'));if(current?.id===pid){current=r.project;const draft=window.mtaMidiEditor?.getDraft();if(id==='instrument'&&draft?.id===trackId)draft.instrument=JSON.parse(JSON.stringify(current.tracks.find(t=>t.id===trackId).instrument));render();timelineAudioDirty=true}}
   closed=true;element.remove();active=null;
   if(owned&&sid)await fetch(`/api/projects/${encodeURIComponent(pid)}/vst3-live/${sid}`,{method:'DELETE',headers:{'X-MTA-Request':'1'}});
  }catch(e){status.textContent=e.message;if(e.status===404){base=null;closing=false;await close();return}timer=setTimeout(tick,500)}finally{closing=false}
 }
 element.querySelector('[data-close]').onclick=close;
 element.addEventListener('keydown',e=>{e.stopPropagation();if(e.key==='Escape'&&e.target!==canvas){e.preventDefault();void close()}});
 function enqueue(event){if(closed||closing||!base)return;if(queue.length>=64){queue=[{type:'release'}];status.textContent=tr('Input queue overflow; controls released','Coda input piena; controlli rilasciati')}queue.push(event);void send()}
 async function send(){if(sending||!base)return;sending=true;try{while(queue.length&&!closed){const batch=queue.splice(0,64);await request(base+'/input',{events:batch})}}catch(e){status.textContent=e.message}finally{sending=false}}
 function point(e){const b=canvas.getBoundingClientRect();return{type:'move',x:Math.min(canvas.width-1,Math.max(0,Math.round((e.clientX-b.left)*canvas.width/b.width))),y:Math.min(canvas.height-1,Math.max(0,Math.round((e.clientY-b.top)*canvas.height/b.height)))}}
 canvas.onpointerdown=e=>{e.preventDefault();canvas.focus();canvas.setPointerCapture(e.pointerId);enqueue(point(e));enqueue({type:'button',button:e.button===2?3:e.button===1?2:1,down:true})};
 canvas.onpointermove=e=>{if(queue.at(-1)?.type==='move')queue[queue.length-1]=point(e);else enqueue(point(e))};
 canvas.onpointerup=e=>{enqueue(point(e));enqueue({type:'button',button:e.button===2?3:e.button===1?2:1,down:false})};canvas.onpointercancel=()=>enqueue({type:'release'});canvas.oncontextmenu=e=>e.preventDefault();canvas.onblur=()=>enqueue({type:'release'});
 canvas.onwheel=e=>{e.preventDefault();enqueue(point(e));const button=e.deltaY<0?4:5;enqueue({type:'button',button,down:true});enqueue({type:'button',button,down:false})};
 for(const name of ['keydown','keyup'])canvas.addEventListener(name,e=>{e.preventDefault();e.stopPropagation();enqueue({type:'key',key:e.key,down:name==='keydown'})});
 async function tick(){
  if(closed||closing||!base)return;
  try{
   const state=await(await request(base+'/state',{})).json();
   if(state.state==='completed'){base=null;if(current?.id===pid){current=state.project;const draft=window.mtaMidiEditor?.getDraft();if(id==='instrument'&&draft?.id===trackId)draft.instrument=JSON.parse(JSON.stringify(current.tracks.find(t=>t.id===trackId).instrument));render();timelineAudioDirty=true}await close();return}
   const r=await request(base+'/frame');const bitmap=await createImageBitmap(await r.blob());if(closed){bitmap.close();return}canvas.width=bitmap.width;canvas.height=bitmap.height;canvas.getContext('2d').drawImage(bitmap,0,0);bitmap.close();status.textContent=tr('Live original editor · changes are saved on close','Editor originale live · modifiche salvate alla chiusura');
  }catch(e){status.textContent=e.message;if(e.status===404){base=null;return}}
  timer=setTimeout(tick,150);
 }
 try{
  collect();await persistCurrentProject(false);
  const audition=window.mtaMidiLive?.session();
  const existing=id==='instrument'&&audition?.tid===trackId?audition:window.mtaServerVst3?.session();
  if(existing?.pid===pid)sid=existing.id;
  else{
   owned=true;const root=`/api/projects/${encodeURIComponent(pid)}/vst3-live`;let r=await(await request(root,{client_id:'editor-'+crypto.randomUUID(),cursor_ms:playCursorMs/tempoRatio()})).json();sid=r.session_id;
   while(r.state==='preparing'&&!closed){await new Promise(resolve=>setTimeout(resolve,250));r=await(await request(root+'/'+sid)).json()}
   if(r.failed)throw Error(r.error);await request(root+'/'+sid+'/control',{action:'pause'});
  }
  const session=`/api/projects/${encodeURIComponent(pid)}/vst3-live/${sid}`;
  const r=await(await request(session+'/editor',{route:trackId||'master',insert:id})).json();base=session+'/editor/'+r.editor_id;canvas.width=r.width;canvas.height=r.height;canvas.focus();void tick();
 }catch(e){status.textContent=e.message;if(owned&&sid)void fetch(`/api/projects/${encodeURIComponent(pid)}/vst3-live/${sid}`,{method:'DELETE',headers:{'X-MTA-Request':'1'}})}
};
})();
