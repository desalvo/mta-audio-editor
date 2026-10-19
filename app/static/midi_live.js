/* Interactive instrument monitoring and local MIDI hardware output. */
(()=>{'use strict';
let access=null,provider='web',monitor=null,starting=null,hardware=null,sequenceTimer=null,lastPlaying=false,lastPosition=0,lastAt=0,hardwareRevision=0,hardwareProject=null;
const padListeners=new Set();let padHandler=null;
const pad={id:'mta-keyboard',name:tr('On-screen keyboard','Tastiera sullo schermo'),addEventListener:(_,fn)=>padListeners.add(fn),removeEventListener:(_,fn)=>padListeners.delete(fn),get onmidimessage(){return padHandler},set onmidimessage(fn){padHandler=fn},emit(data){const e={data,timeStamp:performance.now(),native_direct:false};padHandler?.(e);for(const fn of padListeners)fn(e)}};
const key=()=>`mta.midi.devices.${currentUser?.id||'local'}.${current?.id||''}`;
function preferences(){try{return JSON.parse(localStorage.getItem(key())||'{}')}catch{return {}}}
function remember(value){try{localStorage.setItem(key(),JSON.stringify({...preferences(),...value}))}catch{}}
const editor=()=>window.mtaMidiEditor?.getDraft();
const status=text=>{const node=document.getElementById('midiLiveStatus');if(node)node.textContent=text};
async function bridge(){const b=await waitForNativeApi();if(!b?.midi_ports)throw Error(tr('Update the native application for MIDI hardware support','Aggiornare l’app nativa per il supporto hardware MIDI'));return b}
function nativePort(name){let handler=null,timer=null,busy=false,opening=false;const listeners=new Set();
 const port={id:name,name,addEventListener:(_,fn)=>{listeners.add(fn);ensure()},removeEventListener:(_,fn)=>{listeners.delete(fn);ensure()},get onmidimessage(){return handler},set onmidimessage(fn){handler=fn;ensure()}};
 async function poll(){if(busy)return;busy=true;try{const result=await(await bridge()).midi_capture_poll();if(!result.connected){throw Error(tr('MIDI input disconnected','Ingresso MIDI scollegato'))}for(const item of result.events||[]){const e={data:item.data,timeStamp:performance.now()-Math.max(0,result.now_ms-item.time_ms),native_direct:!!result.monitoring};handler?.(e);for(const fn of listeners)fn(e)}}catch(e){clearInterval(timer);timer=null;status(e.message);void stopMonitor()}finally{busy=false}}
 async function ensure(){if(handler||listeners.size){if(timer||opening)return;opening=true;try{await(await bridge()).midi_capture_start(name,!!preferences().sysex);timer=setInterval(()=>void poll(),16)}catch(e){status(e.message)}finally{opening=false}}else{clearInterval(timer);timer=null;try{await(await bridge()).midi_capture_stop()}catch{}}}
 return port;
}
async function connect(){
 if(access)return access;
 if(currentUser?.native_single_user){
  try{const b=await bridge(),ports=await b.midi_ports();if(ports.available){provider='native';const inputs=new Map(ports.inputs.map(name=>[name,nativePort(name)])),outputs=new Map(ports.outputs.map(name=>[name,MtaNativeMidiOutput.create(name,b,e=>status(e.message))]));inputs.set(pad.id,pad);access={inputs,outputs};return access}}catch{}}
 if(navigator.requestMIDIAccess){const result=await navigator.requestMIDIAccess({sysex:!!preferences().sysex});provider='web';access={inputs:new Map([...result.inputs,...[[pad.id,pad]]]),outputs:result.outputs};result.addEventListener?.('statechange',()=>{void panic();if(monitor)void stopMonitor();refreshSelectors()});return access}
 provider='none';access={inputs:new Map([[pad.id,pad]]),outputs:new Map()};return access;
}
window.mtaRequestMidiAccess=async()=>{
 const all=await connect(),id=preferences().input||pad.id,port=all.inputs.get(id)||pad;
 const fallback=!preferences().input?[...all.inputs.values()].find(x=>x!==pad):null;const chosen=fallback||port;return {...all,inputs:new Map(chosen===pad?[[pad.id,pad]]:[[pad.id,pad],[chosen.id,chosen]])};
};
window.mtaMidiOptions=()=>{
 const p=preferences();if(p.provider!=='native'&&provider!=='native'&&!Object.values(p.ump_outputs||{}).some(Boolean))return {};
 return {outputs:p.outputs||{},ump_outputs:p.ump_outputs||{},sysex:!!p.sysex,clock:!!p.clock};
};
function refreshSelectors(){const input=document.getElementById('midiLiveInput'),output=document.getElementById('midiLiveOutput');if(!input||!output)return;const p=preferences();input.replaceChildren();for(const port of access?.inputs.values()||[pad]){const option=document.createElement('option');option.value=port.id;option.textContent=port.name;input.appendChild(option)}input.value=p.input||pad.id;if(!input.value)input.value=pad.id;
 output.replaceChildren();const none=document.createElement('option');none.value='';none.textContent=tr('Select output…','Selezionare uscita…');output.appendChild(none);for(const port of access?.outputs.values()||[]){const option=document.createElement('option');option.value=port.id;option.textContent=port.name;output.appendChild(option)}output.value=p.outputs?.[editor()?.id]||'';
}
function outputFor(tid){return access?.outputs.get(preferences().outputs?.[tid])}
function send(port,data,when){try{port?.send(data,when)}catch(e){status(e.message);void stopMonitor();void panic()}}
function panicPort(port){if(!port)return;try{port.clear?.();if(port.native)return;for(let ch=0;ch<16;ch++)for(const cc of [64,120,123])port.send([176|ch,cc,0])}catch{}}
async function panic(){for(const id of new Set(Object.values(preferences().outputs||{})))panicPort(access?.outputs.get(id));if(monitor?.native)try{await(await bridge()).midi_monitor_control('panic')}catch{}else if(monitor?.socket?.readyState===1)monitor.socket.send(JSON.stringify({op:'panic'}));}
function handleInput(e){const m=[...e.data];if(m[0]<128||(m[0]>239&&!(preferences().sysex&&m[0]===240&&m.at(-1)===247)))return;const draft=editor();if(!draft||!monitor)return;
 if(draft.midi_route!=='instrument')send(outputFor(draft.id),m);
 if(monitor.native){if(!e.native_direct)void bridge().then(b=>b.midi_monitor_control('midi',[m])).catch(e=>status(e.message))}
 else if(monitor.socket?.readyState===1)monitor.socket.send(JSON.stringify({op:'midi',messages:[m]}));
}
async function stopMonitor(){if(starting)starting.cancelled=true;const s=monitor;monitor=null;window.mtaMidiEditor?.stopRecording();padListeners.delete(handleInput);s?.input?.removeEventListener?.('midimessage',handleInput);clearInterval(s?.timer);clearTimeout(s?.pullTimer);for(const node of s?.sources||[])try{node.stop();node.disconnect()}catch{}
 if(s?.native)try{await(await bridge()).midi_monitor_stop()}catch{}
 if(s?.socket){if(s.socket.readyState===1)s.socket.send(JSON.stringify({op:'stop'}));s.socket.close()}
 await panic();const button=document.getElementById('midiMonitorToggle');if(button)button.textContent=tr('Start monitoring','Avvia monitoring');status(tr('Monitoring stopped','Monitoring fermato'));
}
function contextForMonitor(){return {sample:Math.max(0,Math.round((playCursorMs||0)/tempoRatio()*Number(current?.sample_rate||44100)/1000)),playing:!!window.playbackActuallyRunning()}}
async function startMonitor(task){if(monitor)return stopMonitor();const d=editor();if(!d)return;
 // Browser activation must occur on this click, before HTTP preparation.
 if(!currentUser?.native_single_user){audioCtx=audioCtx||new(window.AudioContext||window.webkitAudioContext)();void audioCtx.resume()}
 status(tr('Preparing monitoring…','Preparazione monitoring…'));document.getElementById('midiMonitorToggle').textContent=tr('Cancel preparation','Annulla preparazione');await window.mtaMidiEditor.save();if(task.cancelled)return;
 const a=(!access&&(!preferences().input||preferences().input===pad.id))?{inputs:new Map([[pad.id,pad]])}:await window.mtaRequestMidiAccess(),p=preferences(),input=[...a.inputs.values()].find(x=>x.id!=='mta-keyboard')||pad;
 if(task.cancelled)return;
 if(editor().midi_route!=='instrument'&&!outputFor(d.id))throw Error(tr('Connect and select a MIDI output','Collegare e selezionare un’uscita MIDI'));
 const s={pid:current.id,tid:d.id,input,sources:new Set(),native:false,nextAt:0,sequence:0};monitor=s;
 try{
  if(editor().midi_route!=='hardware'){
   const capability=await api('/api/vst3/plugins');if(capability.engine!=='cpp'||!capability.host_transport)throw Error(tr('Select C++ and update the VST transport runtime','Selezionare C++ e aggiornare il runtime VST del transport'));
   if(currentUser?.native_single_user){const b=await bridge();s.native=true;await b.midi_monitor_start(current.id,d.id,{input:provider==='native'&&input!==pad?input.id:'',sysex:!!p.sysex})}
   else await new Promise((resolve,reject)=>{
    const endpoint=new URL(`/api/projects/${encodeURIComponent(current.id)}/midi-monitor/${encodeURIComponent(d.id)}`,location.href);if(p.sysex)endpoint.searchParams.set('sysex','1');endpoint.protocol=location.protocol==='https:'?'wss:':'ws:';const ws=s.socket=new WebSocket(endpoint);ws.binaryType='arraybuffer';
    const request=()=>{if(monitor!==s||ws.readyState!==1)return;const queued=s.nextAt-audioCtx.currentTime;if(queued>.045){s.pullTimer=setTimeout(request,4);return}s.sentAt=performance.now();ws.send(JSON.stringify({op:'pull',sequence:s.sequence}))};
    ws.onmessage=e=>{if(monitor!==s)return;
     if(typeof e.data==='string'){const data=JSON.parse(e.data);if(data.state==='failed'){reject(Error(data.error));status(data.error);void stopMonitor()}else if(data.state==='ready'){s.id=data.session_id;s.rate=data.rate;s.nextAt=audioCtx.currentTime+.015;resolve();request()}return}
     const view=new DataView(e.data),frames=view.getUint32(0,true),rate=view.getUint32(4,true);if(rate!==s.rate||frames!==1024||e.data.byteLength!==8+frames*8){status('Invalid MIDI audio stream');void stopMonitor();return}s.sequence++;
     const buffer=audioCtx.createBuffer(2,frames,rate);for(let ch=0;ch<2;ch++){const channel=buffer.getChannelData(ch);for(let i=0;i<frames;i++){const v=view.getFloat32(8+(i*2+ch)*4,true);if(!Number.isFinite(v)){void stopMonitor();return}channel[i]=v}}
     const node=audioCtx.createBufferSource();node.buffer=buffer;node.connect(audioCtx.destination);s.nextAt=Math.max(s.nextAt,audioCtx.currentTime+.005);node.start(s.nextAt);s.nextAt+=frames/rate;s.sources.add(node);node.onended=()=>{s.sources.delete(node);node.disconnect()};status(tr('Monitoring · buffered audio ','Monitoring · audio accodato ')+Math.round((s.nextAt-audioCtx.currentTime+(audioCtx.baseLatency||0))*1000)+' ms · RTT '+Math.round(performance.now()-s.sentAt)+' ms');request();
    };
    ws.onerror=()=>reject(Error(tr('MIDI monitoring connection failed','Connessione monitoring MIDI fallita')));ws.onclose=()=>{reject(Error(tr('MIDI monitoring disconnected','Monitoring MIDI scollegato')));if(monitor===s)void stopMonitor()};
   });
  }
  if(monitor!==s){if(s.native)await(await bridge()).midi_monitor_stop();return}
  padListeners.add(handleInput);if(input!==pad)input.addEventListener('midimessage',handleInput);
  s.timer=setInterval(()=>{if(current?.id!==s.pid||!document.getElementById('midiLivePanel')){void stopMonitor();return}const context=contextForMonitor();if(s.native)void bridge().then(b=>b.midi_monitor_control('transport',context)).catch(e=>{status(e.message);void stopMonitor()});else if(s.socket?.readyState===1)s.socket.send(JSON.stringify({op:'transport',...context}))},200);
  document.getElementById('midiMonitorToggle').textContent=tr('Stop monitoring','Ferma monitoring');if(s.native)status(tr('Native monitoring · device buffer + DSP latency','Monitoring nativo · buffer dispositivo + latenza DSP'));
 }catch(e){if(monitor===s)await stopMonitor();throw e}
}
function mount(){const host=document.querySelector('.midi-editor');if(!host)return;const d=editor(),p=preferences();const panel=document.createElement('section');panel.id='midiLivePanel';panel.className='midi-live-panel';panel.innerHTML=`<div class="midi-toolbar"><label>${tr('MIDI destination','Destinazione MIDI')}<select id="midiRoute"><option value="instrument">VSTi</option><option value="hardware">MIDI hardware</option><option value="both">VSTi + MIDI hardware</option></select></label><button id="midiConnect" class="utility-btn">${tr('Connect MIDI devices','Collega dispositivi MIDI')}</button><label>${tr('Input','Ingresso')}<select id="midiLiveInput"></select></label><label>${tr('Output','Uscita')}<select id="midiLiveOutput"></select></label><label><input id="midiSendClock" type="checkbox" ${p.clock?'checked':''}> MIDI Clock / Start / Stop (24 PPQ)</label></div><div class="midi-toolbar"><button id="midiMonitorToggle" class="primary">${tr('Start monitoring','Avvia monitoring')}</button><button id="midiPanic" class="danger">Panic</button><span id="midiLiveStatus" role="status"></span></div><div id="midiPad" class="midi-toolbar" aria-label="MIDI keyboard"></div><p class="hint">${tr('Monitoring uses a separate audition bus. Server monitoring includes network latency. Hardware MIDI produces external sound, which is not captured in audio exports. Host tempo and time signature follow the project grid.','Il monitoring usa un bus di ascolto separato. Sul server comprende la latenza della rete. Il MIDI hardware produce audio esterno, che non viene acquisito negli export audio. Tempo e misura host seguono la griglia del progetto.')}</p>`;
 host.insertBefore(panel,host.firstChild);document.getElementById('midiRoute').value=d.midi_route||'instrument';refreshSelectors();
 document.getElementById('midiRoute').onchange=e=>{editor().midi_route=e.target.value;void stopMonitor()};
 document.getElementById('midiConnect').onclick=async()=>{try{access=null;await connect();refreshSelectors();status(tr('MIDI devices connected','Dispositivi MIDI collegati'))}catch(e){status(e.message)}};
 document.getElementById('midiLiveInput').onchange=e=>{remember({input:e.target.value,provider});void stopMonitor()};
 document.getElementById('midiLiveOutput').onchange=e=>{remember({outputs:{...preferences().outputs,[d.id]:e.target.value},provider});window.timingAudioChanged([d.id])};
 document.getElementById('midiSendClock').onchange=e=>{remember({clock:e.target.checked,provider});window.timingAudioChanged([d.id])};
 document.getElementById('midiMonitorToggle').onclick=async()=>{if(starting){await stopMonitor();return}const task=starting={cancelled:false};try{await startMonitor(task)}catch(e){status(e.message)}finally{if(starting===task)starting=null;const button=document.getElementById('midiMonitorToggle');if(button&&!monitor)button.textContent=tr('Start monitoring','Avvia monitoring')}};document.getElementById('midiPanic').onclick=()=>void panic();
 const labels=['C','C♯','D','D♯','E','F','F♯','G','G♯','A','A♯','B'];for(let i=0;i<12;i++){const button=document.createElement('button');button.type='button';button.textContent=labels[i]+'4';button.dataset.midiNote=String(60+i);button.onpointerdown=e=>{e.preventDefault();button.setPointerCapture(e.pointerId);pad.emit([144,60+i,100])};button.onpointerup=button.onpointercancel=()=>pad.emit([128,60+i,0]);document.getElementById('midiPad').appendChild(button)}
}
const open=window.openMidiEditor;window.openMidiEditor=async function(...args){if(monitor)await stopMonitor();await open(...args);mount()};
const close=window.closeUtilityModal;window.closeUtilityModal=function(...args){void stopMonitor();return close.apply(this,args)};
window.mtaMidiLive={stop:stopMonitor,panic,parameter(params){if(monitor?.native)void bridge().then(b=>b.midi_monitor_control('midi-parameters',params)).catch(e=>status(e.message));else if(monitor?.socket?.readyState===1)monitor.socket.send(JSON.stringify({op:'parameters',params}))}};
function hardwareRoutes(){return (current?.tracks||[]).filter(t=>t.kind==='midi'&&t.midi_route!=='instrument'&&!t.mute&&(!(current.tracks.some(x=>x.solo))||t.solo))}
function stopHardware(){if(hardware)for(const route of hardware.routes)panicPort(route.port);hardware=null;lastPlaying=false}
function scheduleHardware(){if(!current)return;const nativeCpp=!!(currentUser?.native_single_user&&(provider==='native'||Object.values(preferences().ump_outputs||{}).some(Boolean))&&nativeAudioEngineIdentity==='cpp');if(nativeCpp){stopHardware();return}const playing=!!window.playbackActuallyRunning(),position=Number(playCursorMs||0),now=performance.now(),ratio=tempoRatio();if(!playing){if(lastPlaying)stopHardware();return}
 const routes=hardwareRoutes();if(hardwareProject!==current){hardwareProject=current;hardwareRevision++}const signature=[current.id,hardwareRevision,current.bpm,current.base_bpm,routes.map(t=>t.id).join(',')].join(':');const jumped=lastPlaying&&Math.abs(position-lastPosition-(now-lastAt)*ratio)>100;
 if(!hardware||hardware.signature!==signature||jumped){stopHardware();hardware={signature,tempo:new MtaTempoMap(current),routes:routes.map(track=>({track,port:outputFor(track.id),events:MtaMidiRules.events(track).filter(e=>e.data[0]!==240||preferences().sysex)}))};for(const route of hardware.routes){route.index=MtaMidiRules.lowerBound(route.events,position);for(const msg of MtaMidiRules.chase(route.events,position))send(route.port,msg);route.tick=Math.ceil(Math.max(0,hardware.tempo.ppq(position))*24);if(preferences().clock){if(position<1)send(route.port,[250]);else{const spp=Math.min(16383,Math.round(Math.max(0,hardware.tempo.ppq(position))*4));send(route.port,[242,spp&127,(spp>>7)&127]);send(route.port,[251])}}}}
 const clockPorts=new Set();const ahead=position+32*ratio,bpm=(current.metronome_bpm||current.bpm)/ratio;
 for(const route of hardware.routes){while(route.index<route.events.length&&route.events[route.index].at<=ahead){const e=route.events[route.index++];send(route.port,e.data,now+Math.max(0,(e.at-position)/ratio))}if(preferences().clock&&!clockPorts.has(route.port)){clockPorts.add(route.port);while(hardware.tempo.time(route.tick/24)<=ahead){const at=hardware.tempo.time(route.tick++/24);send(route.port,[248],now+Math.max(0,(at-position)/ratio))}}}
 lastPlaying=true;lastPosition=position;lastAt=now;
}
const timingChanged=window.timingAudioChanged;window.timingAudioChanged=function(...args){hardwareRevision++;return timingChanged.apply(this,args)};
window.mtaMidiLive={...window.mtaMidiLive,session:()=>monitor?.id?{pid:monitor.pid,id:monitor.id,tid:monitor.tid}:null,stop:stopMonitor,preferences,remember,reconnect:()=>{access=null},ump:messages=>{if(monitor?.native)return bridge().then(b=>b.midi_monitor_control('ump',messages));if(monitor?.socket?.readyState===1)monitor.socket.send(JSON.stringify({op:'ump',messages}));}};
sequenceTimer=setInterval(scheduleHardware,8);
const preview=window.previewMaster;window.previewMaster=async function(...args){if(hardwareRoutes().length){try{const ump=preferences().ump_outputs||{},nativeUmp=currentUser?.native_single_user&&nativeAudioEngineIdentity==='cpp';if(!nativeUmp||hardwareRoutes().some(t=>!ump[t.id]))await connect();if(hardwareRoutes().some(t=>!outputFor(t.id)&&!(nativeUmp&&ump[t.id])))throw Error(tr('Connect/select each hardware MIDI output before playback','Collegare/selezionare ogni uscita MIDI hardware prima della riproduzione'))}catch(e){toast(e.message);return}}return preview.apply(this,args)};
for(const name of ['stopPlayback','pausePlayback']){const old=window[name];window[name]=function(...args){if(hardware&&preferences().clock)for(const route of hardware.routes)send(route.port,[252]);stopHardware();return old.apply(this,args)}}
window.addEventListener('blur',()=>{if(monitor)void panic()});window.addEventListener('beforeunload',()=>{clearInterval(sequenceTimer);stopHardware();void stopMonitor()});
})();
