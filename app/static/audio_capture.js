/* Client hardware recording, streamed in bounded PCM packets to durable import. */
(()=>{'use strict';let recording=null;
const json=async(path,body,method='POST')=>{const r=await fetch(path,{method,signal:AbortSignal.timeout(15000),headers:{'Content-Type':'application/json','X-MTA-Request':'1'},body:body===undefined?undefined:JSON.stringify(body)});if(!r.ok){let e;try{e=(await r.json()).detail}catch{}throw Error(e||r.statusText)}return r.json()};
window.openAudioCapture=async function(){
 if(!current)return toast(tr('Open a project first','Aprire prima un progetto'));
 if(recording)return;
 const pid=current.id;let ports=[],native=!!currentUser?.native_single_user,b=null;
 try{if(native){b=await waitForNativeApi();ports=(await b.audio_capture_ports()).map(name=>({id:name,name}))}else{const access=await navigator.mediaDevices.getUserMedia({audio:true});access.getTracks().forEach(t=>t.stop());ports=(await navigator.mediaDevices.enumerateDevices()).filter(d=>d.kind==='audioinput').map(d=>({id:d.deviceId,name:d.label||tr('Audio input','Ingresso audio')}))}
 showUtilityModal(tr('Record external audio','Registra audio esterno'),`<div class="form-grid"><label>${tr('Audio input','Ingresso audio')}<select id="captureInput">${ports.map(p=>`<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('')}</select></label><label>${tr('Track name','Nome traccia')}<input id="captureName" value="${tr('Audio recording','Registrazione audio')}"></label><label>${tr('Input latency compensation (ms)','Compensazione latenza ingresso (ms)')}<input id="captureLatency" type="number" min="0" max="10000" value="0"></label><label><input type="checkbox" id="capturePlay">${tr('Play project while recording','Riproduci il progetto durante la registrazione')}</label><p class="hint">${tr('The selected local input is recorded. External MIDI instruments require an audio cable or loopback input. Input monitoring is disabled to prevent feedback.','Viene registrato l’ingresso locale selezionato. Gli strumenti MIDI esterni richiedono un collegamento audio o un ingresso loopback. Il monitoring dell’ingresso è disattivato per evitare feedback.')}</p><div class="form-actions"><button id="captureStart" class="accent">● ${tr('Record','Registra')}</button><button id="captureStop" disabled>■ ${tr('Stop and save','Ferma e salva')}</button><button id="captureCancel">${tr('Cancel','Annulla')}</button></div><p id="captureStatus" role="status"></p></div>`);
 let state=null;
 const status=text=>{const el=document.getElementById('captureStatus');if(el)el.textContent=text};
 async function stop(save){
  const s=state;if(!s)return closeUtilityModal();if(s.stopping)return;s.stopping=true;clearInterval(s.timer);
  try{
   if(!s.deviceStopped){s.deviceStopped=true;if(s.native){try{const part=await b.audio_capture_read();if(part.frames)enqueue(s,decode(part.pcm))}catch(e){s.error=s.error||e.message}await b.audio_capture_stop()}
   else{s.source?.disconnect();if(s.node){s.node.port.postMessage('flush');await new Promise(resolve=>{s.flushed=resolve;setTimeout(resolve,1000)})}s.node?.disconnect();s.stream?.getTracks().forEach(t=>t.stop());await s.context?.close()}}
   await s.pending;
   if(save){if(s.error){const recovered=await json(s.url,undefined,'GET');s.sequence=recovered.sequence;s.frames=recovered.frames}status(tr('Saving recording to project…','Salvataggio registrazione nel progetto…'));const result=await json(s.url+'/finish',{sequence:s.sequence,name:s.name});
    for(;;){const job=await api('/api/media-jobs/'+result.id);if(job.status==='failed')throw Error(job.error||job.message);if(job.status==='completed'){if(current?.id===pid){current=await api('/api/projects/'+pid);render();timelineAudioDirty=true}break}await new Promise(r=>setTimeout(r,300))}
    toast(s.error?tr('Recorded portion saved: ','Parte registrata salvata: ')+s.error:tr('Recording saved','Registrazione salvata'));closeUtilityModal();
   }else{await json(s.url,undefined,'DELETE');closeUtilityModal()}
   state=recording=null;
  }catch(e){status(e.message);s.stopping=false;document.getElementById('captureCancel')?.removeAttribute('disabled');if(!save){state=recording=null;closeUtilityModal()}}
 }
 function decode(encoded){const raw=atob(encoded),a=new Uint8Array(raw.length);for(let i=0;i<raw.length;i++)a[i]=raw.charCodeAt(i);return a.buffer}
 function enqueue(s,buffer){
  if(s.error)return;if(s.queued+buffer.byteLength>s.rate*8*2){s.error=tr('The upload connection is too slow. Recording stopped to avoid missing audio.','Connessione di upload troppo lenta. Registrazione fermata per evitare audio mancante.');void stop(true);toast(s.error);return}
  s.queued+=buffer.byteLength;s.pending=s.pending.then(async()=>{if(s.error)return;const r=await fetch(s.url+'/pcm?sequence='+s.sequence,{method:'POST',signal:AbortSignal.timeout(10000),headers:{'Content-Type':'application/octet-stream','X-MTA-Request':'1'},body:buffer});if(!r.ok){const v=await r.json();throw Error(v.detail||r.statusText)}const v=await r.json();s.sequence=v.sequence;s.frames=v.frames;status((s.frames/s.rate).toFixed(1)+' s · '+tr('Recording','Registrazione'));}).catch(e=>{s.error=e.message;status(e.message);void stop(true)}).finally(()=>s.queued-=buffer.byteLength)
 }
 document.getElementById('captureCancel').onclick=()=>void stop(false);
 document.getElementById('captureStop').onclick=()=>void stop(true);
 document.getElementById('captureStart').onclick=async()=>{
  let s;
  try{
   const name=document.getElementById('captureName').value,input=document.getElementById('captureInput').value,latency=Math.max(0,Math.min(10000,Number(document.getElementById('captureLatency').value)||0)),play=document.getElementById('capturePlay').checked;
   s={pid,native,name,stop,rate:Number(current.sample_rate||48000),sequence:0,frames:0,queued:0,pending:Promise.resolve(),stopping:false};state=recording=s;
   if(native){if(play&&nativeAudioEngineIdentity==='cpp'){const ready=await window.previewMaster({start_playing:false});if(!ready?.prepared)throw Error(tr('Playback preparation was interrupted','Preparazione riproduzione interrotta'));s.preparedDuplex=true}await b.audio_capture_start(input,s.rate);}
   else{s.stream=await navigator.mediaDevices.getUserMedia({audio:{deviceId:input?{exact:input}:undefined,echoCancellation:false,noiseSuppression:false,autoGainControl:false}});s.context=new AudioContext({sampleRate:s.rate});s.rate=s.context.sampleRate;await s.context.audioWorklet.addModule('/static/audio_capture_worklet.js?v=r210');s.source=s.context.createMediaStreamSource(s.stream);s.node=new AudioWorkletNode(s.context,'mta-audio-capture',{numberOfOutputs:0});s.node.port.onmessage=e=>{if(e.data==='flushed')s.flushed?.();else enqueue(s,e.data)};await s.context.resume()}
   const created=await json(`/api/projects/${encodeURIComponent(pid)}/audio-capture`,{rate:s.rate,offset_ms:Math.max(0,Math.round(playCursorMs-latency))});s.url=`/api/projects/${encodeURIComponent(pid)}/audio-capture/${created.capture_id}`;
   if(native){let busy=false;s.timer=setInterval(async()=>{if(busy||s.stopping)return;busy=true;try{const part=await b.audio_capture_read();if(part.frames)enqueue(s,decode(part.pcm))}catch(e){s.error=e.message;status(e.message);await b.audio_capture_stop()}finally{busy=false}},20)}else s.source.connect(s.node);
   document.getElementById('captureStart').disabled=true;document.getElementById('captureStop').disabled=false;if(play){if(s.preparedDuplex)await window.resumePlayback();else await window.previewMaster()}status(tr('Recording…','Registrazione…'));
  }catch(e){status(e.message);if(s){s.stream?.getTracks().forEach(t=>t.stop());if(native)try{await b.audio_capture_stop()}catch{}if(s.url)await json(s.url,undefined,'DELETE').catch(()=>{});}state=recording=null}
 };
 }catch(e){toast(e.message)}
};
const closeModal=window.closeUtilityModal;window.closeUtilityModal=function(...args){if(recording&&!recording.stopping){if(confirm(tr('Recording is active. Stop and save before closing?','Registrazione attiva. Fermare e salvare prima di chiudere?')))void recording.stop(true);return}return closeModal.apply(this,args)};
window.addEventListener('beforeunload',e=>{if(recording){e.preventDefault();e.returnValue=''}});
const mount=()=>{const bar=document.getElementById('playMaster')?.parentElement;if(!bar||document.getElementById('audioCaptureOpen'))return;const button=document.createElement('button');button.id='audioCaptureOpen';button.className='recording-button';button.textContent='●';button.title=tr('Record external audio','Registra audio esterno');button.setAttribute('aria-label',button.title);button.onclick=window.openAudioCapture;bar.appendChild(button)};
new MutationObserver(mount).observe(document.body,{subtree:true,childList:true});mount();
})();
