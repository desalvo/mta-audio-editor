/* Browser playback of the server's persistent, isolated VST3/C++ graph. */
(()=>{'use strict';
const names=['previewMaster','stopPlayback','pausePlayback','resumePlayback','togglePlayback','playbackActuallyRunning','goToTimestamp','seekTransport','goTransportStart','timingAudioChanged','updatePlaybackGains','queueLiveFxRefresh'];
const old=Object.fromEntries(names.map(n=>[n,window[n]]));
const workletModules=new WeakMap();
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
 if(s.node){const r=s.reported;if(!r||r.buffering||r.ended)return s.cursor;return Math.min(r.frame+Math.max(0,audioCtx.currentTime-r.contextTime)*s.rate,r.frame+r.queued)*1000/s.rate}
 const now=audioCtx.currentTime;let position=s.cursor;
 for(const item of s.sources){if(now>=item.at)position=Math.max(position,(item.frame+Math.min(item.frames,Math.max(0,(now-item.at)*s.rate)))*1000/s.rate)}
 return position;
}
function display(s){
 if(live!==s)return;
 if(!s.paused){s.cursor=cursor(s);playCursorMs=s.cursor*tempoRatio();setPlayCursor(playCursorMs);updateTimedPlaybackOverlay(playCursorMs)}
 if(current?.realtime_meter_enabled&&s.node)MtaPlaybackPrep.paintMeters(current,s.meters,s.paused||s.buffering);
 else if(current?.realtime_meter_enabled){const audible=s.sources.find(item=>audioCtx.currentTime>=item.at&&audioCtx.currentTime<item.at+item.frames/s.rate);MtaPlaybackPrep.paintMeters(current,audible?.meters,s.paused||!audible)}
 if(!s.node&&s.done&&audioCtx.currentTime>=s.nextAt&&!s.paused){window.stopPlayback();return}
 s.raf=requestAnimationFrame(()=>display(s));
}
function discard(s){
 clearInterval(s.heartbeat);cancelAnimationFrame(s.raf);cleanupSources(s);s.cancelled=true;
 s.worker?.terminate();try{s.node?.disconnect();s.node?.port.close()}catch{}
 for(const reply of s.pauseWaiters?.values()||[])reply.reject(Error('Audio session stopped'));s.pauseWaiters?.clear();
 if(s.id)void fetch(url(s),{method:'DELETE',headers:{'X-MTA-Request':'1'},keepalive:true}).catch(()=>{});
}
async function pump(s,token){
 if(s.pumping)return;s.pumping=true;
 try{
  while(live===s&&!s.paused&&!s.done&&token===s.generation){
   if(s.nextAt-audioCtx.currentTime>(s.lookahead||.3)){await new Promise(r=>setTimeout(r,20));continue}
   const requestedAt=performance.now();
   const response=await fetch(url(s)+'/pcm',{method:'POST',headers:{'Content-Type':'application/json','X-MTA-Request':'1'},body:JSON.stringify({sequence:s.sequence,frames:s.chunkFrames||4096}),cache:'no-store'});
   if(!response.ok){let message;try{message=(await response.json()).detail}catch{message=response.statusText}throw Error(message||'VST3 stream failed')}
   const bytes=await response.arrayBuffer();
   // Keep a small queue on a fast LAN, but allow longer chunks on slow links
   // so HTTP round trips do not cause a gap for every audio block.
   const elapsed=(performance.now()-requestedAt)/1000;s.roundTrip=s.roundTrip===undefined?elapsed:s.roundTrip*.8+elapsed*.2;
   s.lookahead=Math.max(.3,Math.min(1.2,s.roundTrip*3+.06));s.chunkFrames=Math.max(4096,Math.min(16384,2**Math.ceil(Math.log2(Math.max(1,s.roundTrip*s.rate*2)))));
   if(live!==s||s.paused||token!==s.generation)return;
   const count=Number(response.headers.get('X-MTA-Frames')),rate=Number(response.headers.get('X-MTA-Rate')),frame=Number(response.headers.get('X-MTA-Start-Frame'));
   const sequence=Number(response.headers.get('X-MTA-Sequence'));
   if(!Number.isInteger(count)||count<0||count>32768||bytes.byteLength!==count*8||rate!==s.rate||sequence!==s.sequence+1||frame!==s.expectedFrame)throw Error(tr('Invalid server audio stream','Flusso audio del server non valido'));
   s.sequence=sequence;s.expectedFrame=frame+count;s.done=response.headers.get('X-MTA-Ended')==='1';
   if(!count){s.done=true;break}
   const values=new DataView(bytes),buffer=audioCtx.createBuffer(2,count,rate);
   for(let ch=0;ch<2;ch++){const channel=buffer.getChannelData(ch);for(let i=0;i<count;i++){const value=values.getFloat32((i*2+ch)*4,true);if(!Number.isFinite(value))throw Error('Non-finite VST3 audio');channel[i]=value}}
   const node=audioCtx.createBufferSource();node.buffer=buffer;node.connect(audioCtx.destination);
   const late=s.nextAt<audioCtx.currentTime;
   const at=s.nextAt>=audioCtx.currentTime?s.nextAt:audioCtx.currentTime+.025,item={node,at,frame,frames:count,meters:JSON.parse(response.headers.get('X-MTA-Meters')||'{}')};s.nextAt=at+count/rate;s.sources.push(item);
   node.onended=()=>{s.cursor=Math.max(s.cursor,(frame+count)*1000/rate);s.sources=s.sources.filter(x=>x!==item);node.disconnect()};node.start(at);
   if(late&&!s.warned){s.warned=true;toast(tr('Server VST3: buffering on this connection. Playback may pause while waiting for audio.','VST3 server: buffering su questa connessione. La riproduzione può fermarsi in attesa dell’audio.'))}
  }
 }catch(e){if(live===s&&token===s.generation){window.stopPlayback();toast(tr('Server VST3 stopped: ','VST3 server interrotto: ')+e.message)}}
 finally{s.pumping=false}
}
async function setupContinuous(s){
 if(!audioCtx.audioWorklet||typeof AudioWorkletNode==='undefined'||typeof Worker==='undefined')return;
 if(!workletModules.has(audioCtx))workletModules.set(audioCtx,audioCtx.audioWorklet.addModule('/static/server_pcm_worklet.js?v=0.3.0-r210-continuous-pcm').catch(error=>{workletModules.delete(audioCtx);throw error}));
 await workletModules.get(audioCtx);
 s.node=new AudioWorkletNode(audioCtx,'mta-server-pcm',{numberOfInputs:0,numberOfOutputs:1,outputChannelCount:[2]});
 s.worker=new Worker('/static/server_pcm_worker.js?v=0.3.0-r210-continuous-pcm');s.pauseWaiters=new Map();s.streamStats={underruns:0};
 const channel=new MessageChannel();s.node.port.postMessage({type:'attach',port:channel.port1},[channel.port1]);s.worker.postMessage({type:'attach',port:channel.port2},[channel.port2]);
 const failed=message=>{if(live!==s)return;window.stopPlayback();toast(tr('Server audio stopped: ','Audio server interrotto: ')+message)};
 s.node.port.onmessage=e=>{const m=e.data;if(m.type==='error'){failed(m.message);return}if(live!==s||m.generation!==s.generation||m.token!==s.nodeToken)return;
  if(m.type==='reset-ready'){const start=s.startRequested;s.startRequested=null;if(start&&!s.paused)s.worker.postMessage(start);return}s.reported=m;s.cursor=m.frame*1000/s.rate;s.meters=m.meters;s.buffering=m.buffering;s.streamStats.underruns=m.underruns;if(m.ended)window.stopPlayback()};
 s.worker.onmessage=e=>{const m=e.data;if(m.type==='paused'){const waiter=s.pauseWaiters.get(m.token);if(waiter){s.pauseWaiters.delete(m.token);waiter.resolve()}return}if(m.type==='error')failed(m.message)};
 s.worker.onerror=e=>failed(e.message||'Audio worker failed');s.node.onprocessorerror=()=>failed('Audio processor failed');s.node.connect(audioCtx.destination);
}
function launchPump(s){
 if(!s.node){s.pumpTask=pump(s,s.generation);return}
 s.reported=null;s.buffering=true;s.nodeToken=crypto.randomUUID();s.startRequested={type:'start',url:url(s),rate:s.rate,frame:s.expectedFrame,sequence:s.sequence,generation:s.generation};
 s.node.port.postMessage({type:'reset',token:s.nodeToken,generation:s.generation,frame:s.expectedFrame,rate:s.rate,paused:false});
}
function pausePull(s){
 if(!s.node)return s.pumpTask;
 const token=crypto.randomUUID();return new Promise((resolve,reject)=>{const timer=setTimeout(()=>{s.pauseWaiters.delete(token);reject(Error('Audio pause timed out'))},15000);s.pauseWaiters.set(token,{resolve:()=>{clearTimeout(timer);resolve()},reject:e=>{clearTimeout(timer);reject(e)}});s.worker.postMessage({type:'pause',token})});
}
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
  const s={id:result.session_id,pid,rate:result.rate,expectedFrame:result.position,sequence:0,cursor:result.position_ms,paused:false,cancelled:false,generation:0,sources:[],nextAt:audioCtx.currentTime+.15,done:false,controls:Promise.resolve(),pumpTask:null};
  pending=s;await setupContinuous(s);
  if(token!==epoch||current?.id!==pid){discard(s);pending=null;return}
  live=s;pending=null;playbackPaused=false;timelineAudioDirty=false;if($('#playMaster'))$('#playMaster').textContent='❚❚';MtaPlaybackPrep.transportButton?.('playing');
  s.heartbeat=setInterval(async()=>{try{const status=await api(url(s));if(live===s&&status.failed)throw Error(status.error||'VST3 worker failed')}catch(e){if(live===s){window.stopPlayback();toast(e.message)}}},3000);
  display(s);launchPump(s);MtaPlaybackPrep.hideProgress(preparation);toast(hasVst()?tr('Server VST3 live playback','Riproduzione VST3 live dal server'):tr('Server C++ live playback','Riproduzione C++ live dal server'));
 }catch(e){if(token===undefined||token===epoch){window.stopPlayback();toast(e.message)}}
 finally{if(pending)discard(pending);preparing=false;setRenderPlaybackPreparing(false);MtaPlaybackPrep.hideProgress(preparation)}
};
window.stopPlayback=function(){
 ++epoch;clearTimeout(refreshTimer);refreshTimer=null;pendingFx=false;const s=live;live=null;
 if(s){playCursorMs=cursor(s)*tempoRatio();discard(s)}
 const result=old.stopPlayback();MtaPlaybackPrep.transportButton?.('stopped');return result;
};
async function seek(s,position,resume){
 s.paused=true;++s.generation;cleanupSources(s);s.cursor=position;playbackPaused=true;MtaPlaybackPrep.transportButton?.('paused');
 const generation=s.generation;
 if(s.node){s.startRequested=null;s.reported=null;s.node.port.postMessage({type:'reset',generation,frame:Math.round(position*s.rate/1000),rate:s.rate,paused:true})}
 // Finish an outstanding pull before resetting sequence/position. HTTP requests
 // may otherwise reach different server threads in an unexpected order.
 await pausePull(s);if(live!==s||generation!==s.generation)return;
 const job=s.controls.catch(()=>{}).then(()=>jsonRequest(url(s)+'/control',{action:'seek',cursor_ms:position,playing:!!resume}));s.controls=job;
 const r=await job;
 if(live!==s||generation!==s.generation)return;
 s.sequence=0;s.expectedFrame=r.status.position;s.cursor=r.status.position_ms;s.done=r.status.ended;s.nextAt=audioCtx.currentTime+.15;s.paused=!resume;playbackPaused=!resume;
 if($('#playMaster'))$('#playMaster').textContent=resume?'❚❚':'▶';MtaPlaybackPrep.transportButton?.(resume?'playing':'paused');
 if(resume){await audioCtx.resume();launchPump(s)}
}
window.pausePlayback=async function(){if(!live)return old.pausePlayback();const s=live;try{await seek(s,cursor(s),false)}catch(e){window.stopPlayback();toast(e.message)}};
window.resumePlayback=async function(){if(!live)return old.resumePlayback();if(timelineAudioDirty)return window.previewMaster();const s=live;try{await seek(s,s.cursor,true)}catch(e){window.stopPlayback();toast(e.message)}};
window.togglePlayback=()=>live?(live.paused?window.resumePlayback():window.pausePlayback()):old.togglePlayback();
window.playbackActuallyRunning=()=>live?!live.paused:old.playbackActuallyRunning();
window.goToTimestamp=function(ms){if(!live)return old.goToTimestamp(ms);const s=live;setPlayCursor(ms);void seek(s,Math.max(0,ms)/tempoRatio(),!s.paused).catch(e=>{window.stopPlayback();toast(e.message)})};
window.seekTransport=delta=>live?window.goToTimestamp(Math.max(0,playCursorMs+delta)):old.seekTransport(delta);
window.goTransportStart=()=>live?window.goToTimestamp(0):old.goTransportStart();
let updating=false,again=false,pendingFx=false;
async function updateLive(){
 if(!live)return;if(updating){again=true;return}updating=true;const s=live;
 try{const fx=pendingFx;pendingFx=false;let body;
  if(fx){collect();await persistCurrentProject(false);body={action:'update'}}
  else body={action:'mixer',mixer:MtaPlaybackPrep.mixerControls(current)};
  if(live!==s)return;const r=await jsonRequest(url(s)+'/control',body);if(live!==s)return;if(r.requires_prepare){const paused=s.paused;await window.previewMaster();if(paused&&live)await window.pausePlayback()}else timelineAudioDirty=false}
 catch(e){if(live===s){window.stopPlayback();toast(e.message)}}finally{updating=false;if(again){again=false;void updateLive()}}
}
function scheduleMixer(){if(!refreshTimer)refreshTimer=setTimeout(()=>{refreshTimer=null;void updateLive()},40)}
for(const name of ['updatePlaybackGains','queueLiveFxRefresh'])window[name]=function(...args){if(!live)return old[name](...args);if(name==='queueLiveFxRefresh')pendingFx=true;scheduleMixer()};
const oldPan=window.setTrackPan;window.setTrackPan=function(...args){const result=oldPan(...args);if(live)scheduleMixer();return result};
window.timingAudioChanged=function(...args){if(!live)return old.timingAudioChanged(...args);timelineAudioDirty=true;clearTimeout(refreshTimer);if(!live.paused)refreshTimer=setTimeout(()=>window.previewMaster(),100)};
window.mtaServerVst3={session:()=>live?{pid:live.pid,id:live.id}:null,stats:()=>live?{mode:live.node?'worklet':'legacy',...live.streamStats}:null};
window.addEventListener('beforeunload',()=>{if(live)discard(live)});
})();
