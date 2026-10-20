/* Native device output is selected exclusively by the C++ preference. */
(()=>{'use strict';let active=false,paused=false,epoch=0,timer=null,busy=false,refreshTimer=null,stopPromise=Promise.resolve(),controls=Promise.resolve(),commandSerial=0,pendingControls=0;
const enabled=()=>currentUser?.native_single_user&&nativeAudioEngineIdentity==='cpp';
const old={};for(const name of ['previewMaster','stopPlayback','pausePlayback','resumePlayback','togglePlayback','goToTimestamp','seekTransport','goTransportStart','playbackActuallyRunning','timingAudioChanged','updatePlaybackGains','queueLiveFxRefresh'])old[name]=window[name];
async function bridge(){const b=await waitForNativeApi();if(!b?.transport_control||!b?.transport_prepare_play)throw Error(tr('This package has no native device transport. Update the native application or select Current engine.','Questo package non include il trasporto audio nativo. Aggiornare l’app o selezionare il motore corrente.'));return b}
function paint(s){playCursorMs=s.position_ms*tempoRatio();setPlayCursor(playCursorMs);updateTimedPlaybackOverlay(playCursorMs);if(current?.realtime_meter_enabled){const meters=s.meters||{master:[s.peak_left,s.peak_right,s.peak_left,s.peak_right]};MtaPlaybackPrep.paintMeters(current,meters,paused)}}
// Serialize bridge commands: a subsequent Play cannot overtake a requested seek.
function queueControl(task,token=epoch){
 const serial=++commandSerial;++pendingControls;
 const job=controls.catch(()=>{}).then(async()=>{if(token!==epoch)return null;const b=await bridge();if(token!==epoch)return null;return task(b)});
 controls=job;return job.then(s=>({s,serial,token}),error=>{if(token===epoch&&serial===commandSerial)throw error;return {s:null,serial,token}}).finally(()=>--pendingControls);
}
function currentReply(reply){return reply.s&&reply.token===epoch&&reply.serial===commandSerial}
async function poll(token){
 if(busy||pendingControls||token!==epoch||!active)return;
 busy=true;const serial=commandSerial;
 try{const s=await(await bridge()).transport_control('status',0);if(token!==epoch||serial!==commandSerial||pendingControls)return;if(s.preparing)return;if(!s.active||s.failed)throw Error(s.error||tr('Native output stopped unexpectedly. Check the system audio device.','Uscita nativa interrotta. Verificare il dispositivo audio di sistema.'));paint(s);if(s.ended)window.stopPlayback()}
 catch(e){if(token===epoch&&serial===commandSerial){window.stopPlayback();toast(e.message)}}finally{busy=false}
}
window.previewMaster=async function(){
 if(!enabled())return old.previewMaster();if(!current?.tracks?.length)return;
 const cursor=playCursorMs,positionRevision=transportPositionRevision,pid=current.id;if(active)window.stopPlayback();else old.stopPlayback();const token=++epoch;setRenderPlaybackPreparing(true);let progressTimer=null;
 const preparation={},started=performance.now();
 try{await stopPromise;if(token!==epoch||current?.id!==pid)return;collect();MtaPlaybackPrep.showProgress(preparation,tr('Preparing audio','Preparazione audio'),-1,tr('Saving project changes','Salvataggio modifiche progetto'));if(projectDirty)await persistCurrentProject(false);const b=await bridge();if(token!==epoch||current?.id!==pid)return;
  if(b.transport_preparation_status)progressTimer=setInterval(async()=>{try{const p=await b.transport_preparation_status();if(token!==epoch)return;const phases={loading:tr('Loading project','Caricamento progetto'),sources:tr('Checking sources / converting incompatible formats','Verifica sorgenti / conversione formati incompatibili'),graph:tr('Starting live DSP and inserts','Avvio DSP live e insert'),mix:tr('Rendering fallback mix','Rendering mix di compatibilità'),ready:tr('Starting output device','Avvio dispositivo di uscita')};MtaPlaybackPrep.showProgress(preparation,tr('Preparing audio','Preparazione audio'),-1,(phases[p.stage]||p.stage)+(p.track?' · '+p.track:''),`${p.done}/${p.total} · ${Math.round((performance.now()-started)/1000)}s`)}catch{}},400);
  const prepared=await queueControl(b=>b.transport_prepare_play(pid,cursor/tempoRatio(),window.mtaMidiOptions?window.mtaMidiOptions():null,false),token);
  if(token!==epoch||current?.id!==pid)return;
  active=true;paused=false;playbackPaused=false;timelineAudioDirty=false;
  let reply=prepared;
  if(positionRevision!==transportPositionRevision){const position=playCursorMs;reply=await queueControl(b=>b.transport_control('seek',position/tempoRatio()),token)}
  if(token!==epoch)return;if(!paused)reply=await queueControl(b=>b.transport_control('play',0),token);
  if(token!==epoch)return;if(currentReply(reply))paint(reply.s);
  MtaPlaybackPrep.transportButton?.(paused?'paused':'playing');timer=setInterval(()=>poll(token),80)

 }catch(e){if(token===epoch){window.stopPlayback();toast(e.message)}}finally{clearInterval(progressTimer);if(token===epoch)setRenderPlaybackPreparing(false);MtaPlaybackPrep.hideProgress(preparation)}
};
window.stopPlayback=function(){++epoch;clearInterval(timer);clearTimeout(refreshTimer);timer=null;refreshTimer=null;pendingFx=false;const was=active;active=false;paused=false;playbackPaused=false;++commandSerial;if(was||enabled()){stopPromise=controls.catch(()=>{}).then(async()=>{const b=await bridge();const r=await b.transport_control('stop',0);if(current?.id===r.project_id){for(const item of r.states||[]){const list=item.route==='master'?current.master_inserts:trackById(item.route)?.inserts;const insert=item.insert==='instrument'?trackById(item.route)?.instrument:list?.find(i=>i.id===item.insert);if(insert?.params?.path===item.params.path)insert.params=item.params}}}).catch(e=>console.warn(e.message));controls=stopPromise}const result=old.stopPlayback();setRenderPlaybackPreparing(false);MtaPlaybackPrep.transportButton?.('stopped');return result};
async function playbackCommand(action){
 const token=epoch;paused=action==='pause';playbackPaused=paused;MtaPlaybackPrep.transportButton?.(paused?'paused':'playing');
 try{const reply=await queueControl(b=>b.transport_control(action,0),token);if(currentReply(reply))paint(reply.s)}catch(e){if(token===epoch){window.stopPlayback();toast(e.message)}}
}
window.pausePlayback=async function(){if(!active)return old.pausePlayback();return playbackCommand('pause')};
window.resumePlayback=async function(){if(!active)return old.resumePlayback();if(timelineAudioDirty)return window.previewMaster();return playbackCommand('play')};
window.togglePlayback=()=>active?(paused?window.resumePlayback():window.pausePlayback()):old.togglePlayback();
window.playbackActuallyRunning=()=>active?!paused:old.playbackActuallyRunning();
window.goToTimestamp=function(ms){
 if(!active)return old.goToTimestamp(ms);
 const target=requestTransportPosition(ms),token=epoch;
 updateTimedPlaybackOverlay(target);
 return queueControl(b=>b.transport_control('seek',target/tempoRatio()),token).then(reply=>{if(currentReply(reply))paint(reply.s)}).catch(e=>{if(token===epoch){window.stopPlayback();toast(e.message)}})
};
window.seekTransport=function(delta){return active?window.goToTimestamp(playCursorMs+delta):old.seekTransport(delta)};
window.goTransportStart=function(){return active?window.goToTimestamp(0):old.goTransportStart()};
let liveUpdating=false,liveAgain=false,pendingFx=false;
async function updateLive(){if(!active)return;if(liveUpdating){liveAgain=true;return}liveUpdating=true;const token=epoch,pid=current?.id;try{const fx=pendingFx;pendingFx=false;if(fx){collect();await persistCurrentProject(false)}if(token!==epoch)return;const b=await bridge();const r=fx?await b.transport_update_live(pid):await b.transport_update_live(pid,MtaPlaybackPrep.mixerControls(current));if(token!==epoch)return;if(r.requires_prepare){if(!paused)await window.previewMaster()}else timelineAudioDirty=false}catch(e){if(token===epoch)toast(e.message)}finally{liveUpdating=false;if(liveAgain){liveAgain=false;void updateLive()}}}
function refresh(timing){if(!active)return;if(timing||pendingFx)timelineAudioDirty=true;if(timing){clearTimeout(refreshTimer);refreshTimer=null;if(paused)return}if(!refreshTimer)refreshTimer=setTimeout(()=>{refreshTimer=null;void(timing?window.previewMaster():updateLive())},40)}
for(const name of ['timingAudioChanged','updatePlaybackGains','queueLiveFxRefresh'])window[name]=function(...args){const result=old[name](...args);if(name==='queueLiveFxRefresh')pendingFx=true;refresh(name==='timingAudioChanged');return result};
const oldPan=window.setTrackPan;window.setTrackPan=function(...args){const result=oldPan(...args);refresh(false);return result};
window.addEventListener('beforeunload',()=>{if(active)void bridge().then(b=>b.transport_control('stop',0))});
})();
