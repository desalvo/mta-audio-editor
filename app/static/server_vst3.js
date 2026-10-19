/* Browser playback of the server's persistent, isolated VST3/C++ graph. */
(()=>{'use strict';
const names=['previewMaster','stopPlayback','pausePlayback','resumePlayback','togglePlayback','playbackActuallyRunning','goToTimestamp','seekTransport','goTransportStart','timingAudioChanged','updatePlaybackGains','queueLiveFxRefresh'];
const old=Object.fromEntries(names.map(n=>[n,window[n]]));
const clientId=crypto.randomUUID();let live=null,epoch=0,refreshTimer=null,preparing=false;
const hasVst=()=>current&&(current.tracks.some(t=>t.kind==='midi')||[current.master_inserts,...current.tracks.map(t=>t.inserts)].some(items=>(items||[]).some(i=>i.enabled&&i.plugin==='vst3')));
const isServer=()=>currentUser&&!currentUser.native_single_user;
const url=s=>`/api/projects/${encodeURIComponent(s.pid)}/vst3-live/${s.id}`;
async function jsonRequest(path,body,method='POST'){
 const response=await fetch(path,{method,headers:{'Content-Type':'application/json','X-MTA-Request':'1'},body:body===undefined?undefined:JSON.stringify(body),cache:'no-store'});
 if(!response.ok){let message;try{message=(await response.json()).detail}catch{message=response.statusText}throw Error(message||'VST3 request failed')}
 return response.json();
}
function cleanupSources(s){for(const item of s.sources)try{item.node.onended=null;item.node.stop();item.node.disconnect()}catch{}s.sources=[]}
function cursor(s){
 if(s.paused)return s.cursor;
 const now=audioCtx.currentTime;let position=s.cursor;
 for(const item of s.sources){if(now>=item.at)position=Math.max(position,(item.frame+Math.min(item.frames,Math.max(0,(now-item.at)*s.rate)))*1000/s.rate)}
 return position;
}
function display(s){
 if(live!==s)return;
 if(!s.paused){s.cursor=cursor(s);playCursorMs=s.cursor*tempoRatio();setPlayCursor(playCursorMs);updateTimedPlaybackOverlay(playCursorMs)}
 if(s.done&&audioCtx.currentTime>=s.nextAt&&!s.paused){window.stopPlayback();return}
 s.raf=requestAnimationFrame(()=>display(s));
}
function discard(s){
 clearInterval(s.heartbeat);cancelAnimationFrame(s.raf);cleanupSources(s);s.cancelled=true;
 if(s.id)void fetch(url(s),{method:'DELETE',headers:{'X-MTA-Request':'1'},keepalive:true}).catch(()=>{});
}
async function pump(s,token){
 if(s.pumping)return;s.pumping=true;
 try{
  while(live===s&&!s.paused&&!s.done&&token===s.generation){
   if(s.nextAt-audioCtx.currentTime>.7){await new Promise(r=>setTimeout(r,20));continue}
   const response=await fetch(url(s)+'/pcm',{method:'POST',headers:{'Content-Type':'application/json','X-MTA-Request':'1'},body:JSON.stringify({sequence:s.sequence,frames:32768}),cache:'no-store'});
   if(!response.ok){let message;try{message=(await response.json()).detail}catch{message=response.statusText}throw Error(message||'VST3 stream failed')}
   const bytes=await response.arrayBuffer();if(live!==s||s.paused||token!==s.generation)return;
   const count=Number(response.headers.get('X-MTA-Frames')),rate=Number(response.headers.get('X-MTA-Rate')),frame=Number(response.headers.get('X-MTA-Start-Frame'));
   const sequence=Number(response.headers.get('X-MTA-Sequence'));
   if(!Number.isInteger(count)||count<0||count>32768||bytes.byteLength!==count*8||rate!==s.rate||sequence!==s.sequence+1||frame!==s.expectedFrame)throw Error(tr('Invalid server audio stream','Flusso audio del server non valido'));
   s.sequence=sequence;s.expectedFrame=frame+count;s.done=response.headers.get('X-MTA-Ended')==='1';
   if(!count){s.done=true;break}
   const values=new DataView(bytes),buffer=audioCtx.createBuffer(2,count,rate);
   for(let ch=0;ch<2;ch++){const channel=buffer.getChannelData(ch);for(let i=0;i<count;i++){const value=values.getFloat32((i*2+ch)*4,true);if(!Number.isFinite(value))throw Error('Non-finite VST3 audio');channel[i]=value}}
   const node=audioCtx.createBufferSource();node.buffer=buffer;node.connect(audioCtx.destination);
   const late=s.nextAt<audioCtx.currentTime;
   const at=Math.max(s.nextAt,audioCtx.currentTime+.08),item={node,at,frame,frames:count};s.nextAt=at+count/rate;s.sources.push(item);
   node.onended=()=>{s.cursor=Math.max(s.cursor,(frame+count)*1000/rate);s.sources=s.sources.filter(x=>x!==item);node.disconnect()};node.start(at);
   if(late&&!s.warned){s.warned=true;toast(tr('Server VST3: buffering on this connection. Playback may pause while waiting for audio.','VST3 server: buffering su questa connessione. La riproduzione può fermarsi in attesa dell’audio.'))}
  }
 }catch(e){if(live===s&&token===s.generation){window.stopPlayback();toast(tr('Server VST3 stopped: ','VST3 server interrotto: ')+e.message)}}
 finally{s.pumping=false}
}
function launchPump(s){s.pumpTask=pump(s,s.generation)}
window.previewMaster=async function(){
 if(!isServer()||!current?.tracks?.length)return old.previewMaster();
 if(preparing){window.stopPlayback();return}preparing=true;
 const preparation={};let token,pending=null;
 try{
  // Unlock on the original Play gesture, before waiting for server requests
  // (required by browsers with stricter audio activation policies).
  audioCtx=audioCtx||new(window.AudioContext||window.webkitAudioContext)();
  const unlocked=audioCtx.resume(),attempt=epoch;
  const [capability]=await Promise.all([api('/api/vst3/plugins'),unlocked]);
  if(attempt!==epoch)return;
  if(capability.engine!=='cpp')return old.previewMaster();
  if(!capability.live_available)throw Error(tr('Ask the administrator to install the server VST3 runtime.','Chiedere all’amministratore di installare il runtime VST3 sul server.'));
  const position=playCursorMs;window.stopPlayback();token=++epoch;setRenderPlaybackPreparing(true);
  collect();MtaPlaybackPrep.showProgress(preparation,tr('Preparing audio','Preparazione audio'),-1,tr('Starting server audio session','Avvio sessione audio sul server'));if(projectDirty)await persistCurrentProject(false);if(token!==epoch)return;
  const pid=current.id;let result=await jsonRequest(`/api/projects/${encodeURIComponent(pid)}/vst3-live`,{client_id:clientId,cursor_ms:position/tempoRatio()});
  pending={id:result.session_id,pid,sources:[]};
  while(result.state==='preparing'){
   if(token!==epoch||current?.id!==pid)return;
   await new Promise(r=>setTimeout(r,300));result=await api(url(pending));
   if(token!==epoch||current?.id!==pid)return;
   const p=result.preparation||{};MtaPlaybackPrep.showProgress(preparation,tr('Preparing audio','Preparazione audio'),-1,(p.stage==='sources'?tr('Checking sources / converting incompatible formats','Verifica sorgenti / conversione formati incompatibili'):tr('Starting live DSP and inserts','Avvio DSP live e insert'))+(p.track?' · '+p.track:''),p.total?`${p.done}/${p.total}`:'');
  }
  if(result.failed)throw Error(result.error||tr('Server VST3 preparation failed','Preparazione VST3 server fallita'));
  const s={id:result.session_id,pid,rate:result.rate,expectedFrame:result.position,sequence:0,cursor:result.position_ms,paused:false,cancelled:false,generation:0,sources:[],nextAt:audioCtx.currentTime+.2,done:false,controls:Promise.resolve(),pumpTask:null};
  if(token!==epoch||current?.id!==pid)return;
  live=s;pending=null;playbackPaused=false;timelineAudioDirty=false;if($('#playMaster'))$('#playMaster').textContent='❚❚';
  s.heartbeat=setInterval(async()=>{try{const status=await api(url(s));if(live===s&&status.failed)throw Error(status.error||'VST3 worker failed')}catch(e){if(live===s){window.stopPlayback();toast(e.message)}}},3000);
  display(s);launchPump(s);MtaPlaybackPrep.hideProgress(preparation);toast(hasVst()?tr('Server VST3 live playback','Riproduzione VST3 live dal server'):tr('Server C++ live playback','Riproduzione C++ live dal server'));
 }catch(e){if(token===undefined||token===epoch){window.stopPlayback();toast(e.message)}}
 finally{if(pending)discard(pending);preparing=false;setRenderPlaybackPreparing(false);MtaPlaybackPrep.hideProgress(preparation)}
};
window.stopPlayback=function(){
 ++epoch;clearTimeout(refreshTimer);const s=live;live=null;
 if(s){playCursorMs=cursor(s)*tempoRatio();discard(s)}
 return old.stopPlayback();
};
async function seek(s,position,resume){
 s.paused=true;++s.generation;cleanupSources(s);s.cursor=position;playbackPaused=true;
 const generation=s.generation;
 // Finish an outstanding pull before resetting sequence/position. HTTP requests
 // may otherwise reach different server threads in an unexpected order.
 await s.pumpTask;if(live!==s||generation!==s.generation)return;
 const job=s.controls.catch(()=>{}).then(()=>jsonRequest(url(s)+'/control',{action:'seek',cursor_ms:position,playing:!!resume}));s.controls=job;
 const r=await job;
 if(live!==s||generation!==s.generation)return;
 s.sequence=0;s.expectedFrame=r.status.position;s.cursor=r.status.position_ms;s.done=r.status.ended;s.nextAt=audioCtx.currentTime+.2;s.paused=!resume;playbackPaused=!resume;
 if($('#playMaster'))$('#playMaster').textContent=resume?'❚❚':'▶';
 if(resume){await audioCtx.resume();launchPump(s)}
}
window.pausePlayback=async function(){if(!live)return old.pausePlayback();const s=live;try{await seek(s,cursor(s),false)}catch(e){window.stopPlayback();toast(e.message)}};
window.resumePlayback=async function(){if(!live)return old.resumePlayback();if(timelineAudioDirty)return window.previewMaster();const s=live;try{await seek(s,s.cursor,true)}catch(e){window.stopPlayback();toast(e.message)}};
window.togglePlayback=()=>live?(live.paused?window.resumePlayback():window.pausePlayback()):old.togglePlayback();
window.playbackActuallyRunning=()=>live?!live.paused:old.playbackActuallyRunning();
window.goToTimestamp=function(ms){if(!live)return old.goToTimestamp(ms);const s=live;setPlayCursor(ms);void seek(s,Math.max(0,ms)/tempoRatio(),!s.paused).catch(e=>{window.stopPlayback();toast(e.message)})};
window.seekTransport=delta=>live?window.goToTimestamp(Math.max(0,playCursorMs+delta)):old.seekTransport(delta);
window.goTransportStart=()=>live?window.goToTimestamp(0):old.goTransportStart();
let updating=false,again=false;
async function updateLive(){
 if(!live)return;if(updating){again=true;return}updating=true;const s=live;
 try{collect();await persistCurrentProject(false);if(live!==s)return;const r=await jsonRequest(url(s)+'/control',{action:'update'});if(live!==s)return;if(r.requires_prepare){const paused=s.paused;await window.previewMaster();if(paused&&live)await window.pausePlayback()}else timelineAudioDirty=false}
 catch(e){if(live===s){window.stopPlayback();toast(e.message)}}finally{updating=false;if(again){again=false;void updateLive()}}
}
for(const name of ['updatePlaybackGains','queueLiveFxRefresh'])window[name]=function(...args){if(!live)return old[name](...args);clearTimeout(refreshTimer);refreshTimer=setTimeout(updateLive,80)};
window.timingAudioChanged=function(...args){if(!live)return old.timingAudioChanged(...args);timelineAudioDirty=true;clearTimeout(refreshTimer);if(!live.paused)refreshTimer=setTimeout(()=>window.previewMaster(),100)};
window.mtaServerVst3={session:()=>live?{pid:live.pid,id:live.id}:null};
window.addEventListener('beforeunload',()=>{if(live)discard(live)});
})();
