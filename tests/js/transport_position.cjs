/* Deterministic races against production transport functions, without audio hardware. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const root=process.cwd(),mode=process.argv[2],cases=[];
const deferred=()=>{let resolve,reject;const promise=new Promise((r,j)=>{resolve=r;reject=j});return {promise,resolve,reject}};
async function settle(){for(let i=0;i<30;i++)await Promise.resolve()}
function context(){
 const timers=[],events=new Map();
 const c={console,performance:{now:()=>0},crypto:{randomUUID:()=>String(Math.random())},setInterval:f=>(timers.push(f),timers.length),clearInterval:()=>{},setTimeout,clearTimeout,requestAnimationFrame:()=>1,cancelAnimationFrame:()=>{},current:{id:'p',tracks:[{}]},currentUser:{native_single_user:false},playCursorMs:1000,transportPositionRevision:0,playbackPaused:false,timelineAudioDirty:false,projectDirty:false,audioCtx:{currentTime:0,resume:async()=>{}},tr:en=>en,$:()=>null,tempoRatio:()=>2,collect:()=>{},updateTimedPlaybackOverlay:()=>{},setRenderPlaybackPreparing:()=>{},toast:e=>{c.errors.push(e)},errors:[],MtaPlaybackPrep:{showProgress:()=>{},hideProgress:()=>{},transportButton:()=>{},paintMeters:()=>{}},addEventListener:(name,fn)=>events.set(name,fn),fetch:async()=>({ok:true,json:async()=>({})})};
 for(const name of ['previewMaster','stopPlayback','pausePlayback','resumePlayback','togglePlayback','seekTransport','goTransportStart','timingAudioChanged','updatePlaybackGains','queueLiveFxRefresh','setTrackPan'])c[name]=()=>{};
 c.playbackActuallyRunning=()=>false;c.setPlayCursor=n=>{c.playCursorMs=n};c.requestTransportPosition=n=>{c.transportPositionRevision++;c.playCursorMs=Math.max(0,Math.round(Number(n)||0));return c.playCursorMs};c.goToTimestamp=n=>c.requestTransportPosition(n);
 c.window=c;c.timers=timers;c.events=events;const result=vm.createContext(c);load(result,'app/static/musical_clock.js');return result;
}
function load(c,path){vm.runInContext(fs.readFileSync(root+'/'+path,'utf8'),c,{filename:path})}
function part(source,a,b){return source.slice(source.indexOf(a),source.indexOf(b,source.indexOf(a)))}
async function native(){
 const c=context(),calls=[],gates={};let position=500,preparation=null;
 c.currentUser.native_single_user=true;c.nativeAudioEngineIdentity='cpp';
 c.waitForNativeApi=async()=>({transport_prepare_play:async(pid,ms,midi,startPlaying)=>{assert.equal(startPlaying,false);calls.push(['prepare',ms]);if(preparation)await preparation.promise;position=ms;return {active:true,position_ms:position}},transport_control:async(action,value)=>{calls.push([action,value]);const snapshot={active:true,position_ms:position};if(gates[action])await gates[action].promise;if(action==='seek')position=value;return action==='status'?snapshot:{active:true,position_ms:position}}});
 load(c,'app/static/native_transport.js');await c.previewMaster();
 c.current.musical_origin_ms=6000;await c.goTransportStart();assert.equal(c.playCursorMs,6000);assert.deepEqual(calls.at(-1),['seek',3000]);delete c.current.musical_origin_ms;cases.push('native return-to-start seeks musical origin with tempo conversion');
 const poll=c.timers.at(-1);gates.status=deferred();const status=poll();await settle();
 const seek=c.goToTimestamp(8000);await seek;assert.equal(c.playCursorMs,8000);gates.status.resolve();await status;assert.equal(c.playCursorMs,8000);delete gates.status;cases.push('native stale status cannot overwrite manual seek');
 gates.seek=deferred();const first=c.goToTimestamp(12000);await settle();const second=c.goToTimestamp(18000);await settle();gates.seek.resolve();await first;assert.equal(c.playCursorMs,18000);await second;assert.equal(c.playCursorMs,18000);delete gates.seek;cases.push('native repeated seeks preserve latest command');
 await c.pausePlayback();gates.seek=deferred();const change=c.goToTimestamp(24000);await settle();const resume=c.resumePlayback();await settle();assert.equal(calls.at(-1)[0],'seek');gates.seek.resolve();await Promise.all([change,resume]);assert.equal(c.playCursorMs,24000);assert.deepEqual(calls.slice(-2),[['seek',12000],['play',0]]);delete gates.seek;cases.push('native seek completes before subsequent Play with tempo conversion');
 const rejected=deferred();gates.seek=rejected;const outdated=c.goToTimestamp(3000);await settle();const newer=c.goToTimestamp(27000);delete gates.seek;rejected.reject(Error('old seek failed'));await Promise.all([outdated,newer]);assert.equal(c.playCursorMs,27000);assert.equal(c.playbackActuallyRunning(),true);cases.push('native obsolete control failure cannot stop newer positioning');
 c.stopPlayback();await settle();preparation=deferred();const pending=c.previewMaster();await settle();c.goToTimestamp(32000);preparation.resolve();await pending;assert.equal(c.playCursorMs,32000);assert.deepEqual(calls.slice(-2),[['seek',16000],['play',0]]);cases.push('native positioning during device preparation wins');
 gates.seek=deferred();const late=c.goToTimestamp(2000);await settle();c.stopPlayback();c.goToTimestamp(9000);gates.seek.resolve();await late;assert.equal(c.playCursorMs,9000);await settle();assert.equal(c.playbackActuallyRunning(),false);cases.push('native stopped session cannot repaint cursor');
 assert.deepEqual(c.errors,[]);
}
async function server(){
 const c=context(),requests=[],gates={},posts=[];let createGate=null,position=500;
 c.api=async()=>({engine:'cpp',live_available:true});
 c.fetch=async(path,options)=>{
  if(options.method==='DELETE')return {ok:true};
  const body=options.body?JSON.parse(options.body):{};requests.push([path,body]);
  if(path.endsWith('/vst3-live')){if(createGate)await createGate.promise;position=body.cursor_ms;return {ok:true,json:async()=>({session_id:'s',rate:48000,position:position*48,position_ms:position})}}
  if(path.endsWith('/control')){if(gates.control)await gates.control.promise;position=body.cursor_ms;return {ok:true,json:async()=>({status:{position:position*48,position_ms:position,ended:false}})}}
  throw Error('Unexpected stream request');
 };
 // Use a minimal worklet endpoint so no PCM or wall-clock timing is involved.
 c.AudioWorkletNode=class {constructor(){this.port={postMessage:m=>posts.push(m),close:()=>{}}}connect(){}disconnect(){}};
 c.Worker=class {postMessage(m){if(m.type==='pause')queueMicrotask(()=>this.onmessage({data:{type:'paused',token:m.token}}))}terminate(){}};
 c.MessageChannel=class {constructor(){this.port1={};this.port2={}}};c.audioCtx.audioWorklet={addModule:async()=>{}};
 load(c,'app/static/server_vst3.js');await c.previewMaster();await c.pausePlayback();
 c.current.musical_origin_ms=6000;await c.goTransportStart();assert.equal(c.playCursorMs,6000);assert.equal(requests.at(-1)[1].cursor_ms,3000);delete c.current.musical_origin_ms;cases.push('server return-to-start seeks musical origin with tempo conversion');
 gates.control=deferred();const one=c.goToTimestamp(6000);await settle();const two=c.goToTimestamp(14000);gates.control.resolve();await Promise.all([one,two]);delete gates.control;assert.equal(c.playCursorMs,14000);assert.equal(requests.at(-1)[1].cursor_ms,7000);assert.equal(requests.at(-1)[1].playing,false);cases.push('server latest seek wins while paused');
 await c.resumePlayback();gates.control=deferred();const a=c.goToTimestamp(20000);await settle();const b=c.goToTimestamp(26000);gates.control.resolve();await Promise.all([a,b]);delete gates.control;assert.equal(requests.at(-1)[1].playing,true);assert.equal(requests.at(-1)[1].cursor_ms,13000);assert.equal(c.playbackActuallyRunning(),true);cases.push('server repeated running seeks keep playback intent');
 c.stopPlayback();createGate=deferred();const prepare=c.previewMaster();await settle();c.goToTimestamp(34000);createGate.resolve();await prepare;assert.equal(requests.at(-1)[1].cursor_ms,17000);assert.equal(c.playCursorMs,34000);createGate=null;cases.push('server session preparation honors latest manual position');
 await c.pausePlayback();gates.control=deferred();const seek=c.goToTimestamp(22000);await settle();const play=c.resumePlayback();gates.control.resolve();await Promise.all([seek,play]);delete gates.control;assert.equal(requests.at(-1)[1].cursor_ms,11000);assert.equal(requests.at(-1)[1].playing,true);cases.push('server pending seek followed by Play uses requested position');
 await c.pausePlayback();const unlock=deferred();c.audioCtx.resume=()=>unlock.promise;const restarting=c.resumePlayback();await settle();await c.pausePlayback();const count=posts.length;unlock.resolve();await restarting;assert.equal(posts.length,count);assert.equal(c.playbackActuallyRunning(),false);cases.push('server late audio unlock cannot restart a paused generation');
 c.stopPlayback();assert.ok(c.errors.every(message=>message==='Server C++ live playback'),JSON.stringify(c.errors));
}
async function web(){
 const source=fs.readFileSync(root+'/app/static/app.js','utf8'),c=context();
 vm.runInContext(`let transportPositionRevision=0;${part(source,'function requestTransportPosition(','function setTransportTime(')}`,c);
 c.waPlaybackActive=true;c.waPlaybackPaused=true;c.waStartCursorMs=500;c.waStopSources=()=>{};c.waScheduleAll=ms=>{c.scheduled=ms;c.waStartCursorMs=ms};c.reanchorTransportClock=()=>{};c.alignDynamicTracks=()=>{};
 c.goToTimestamp(12000);assert.equal(c.waStartCursorMs,12000);assert.equal(c.playCursorMs,12000);cases.push('WebAudio paused seek updates clock anchor');
 c.waPlaybackPaused=false;c.goToTimestamp(17000);assert.equal(c.scheduled,17000);cases.push('WebAudio running seek schedules requested offset');
 const nodes={};c.$=s=>nodes[s]||null;c.$$=()=>[];c.followPlayhead=()=>{};
 const pane=nodes['#timelinePane']={scrollLeft:100,getBoundingClientRect:()=>({left:10})},lanes=nodes['#lanes']={addEventListener:()=>{}},ruler=nodes['#ruler']={};
 c.rememberSampleRange=()=>{};c.selectedTimelineSegments=new Set();c.paintSegmentSelection=()=>{};c.updateSel=()=>{};c.timelineTool='select';c.pxPerSec=100;c.sel={a:0,b:0};c.splitSelectedTracksAt=()=>{};c.dragging=false;
 vm.runInContext(part(source,'function bindTimeline(){','function updateSel()'),c);c.bindTimeline();
 const event={button:0,clientX:410,preventDefault:()=>{}};lanes.onmousedown(event);assert.equal(c.scheduled,5000);ruler.onclick({...event,clientX:610});assert.equal(c.scheduled,7000);
 c.timelineTool='range';lanes.onmousedown({...event,clientX:810});c.onmouseup(event);assert.equal(c.scheduled,9000);cases.push('timeline Select, Range and ruler clicks seek the audio engine');
 vm.runInContext(part(source.slice(source.lastIndexOf('function seekTransport(deltaMs)')),'function seekTransport(deltaMs)','async function previewMaster()'),c);c.seekTransport(1000);assert.equal(c.scheduled,10000);c.goTransportStart();assert.equal(c.scheduled,0);c.current.musical_origin_ms=2500;c.goTransportStart();assert.equal(c.scheduled,2500);delete c.current.musical_origin_ms;cases.push('arrow and start commands seek zero or musical origin through manual-position path');
 const clip={id:'c',timeline_start_ms:0,source_start_ms:0,source_end_ms:30000},track={id:'t',clips:[clip]};
 c.trackById=()=>track;c.selectedSegmentItems=()=>[{track,clip}];c.MtaTimelineRules={key:()=> 't:c',delta:(_p,_s,wanted)=>wanted};c.CSS={escape:s=>s};c.cancelTrackContextLongPress=()=>{};c.focusTrackShortcuts=()=>{};c.drawWave=()=>{};
 c.document={body:{classList:{add:()=>{},remove:()=>{}}},querySelector:()=>null};c.removeEventListener=(name,fn)=>{if(c.events.get(name)===fn)c.events.delete(name)};c.moveSelectedSegments=()=>{c.moved=true};c.timelineTool='select';c.selectedTimelineSegments.clear();
 vm.runInContext(part(source,'function beginTimelineClipDrag(','function refreshTimelineToolControls('),c);
 const pointer={...event,pointerId:1,stopPropagation:()=>{}};c.beginTimelineClipDrag(pointer,'t','c');c.events.get('pointerup')(pointer);assert.equal(c.scheduled,5000);
 c.beginTimelineClipDrag(pointer,'t','c');c.events.get('pointermove')({...pointer,clientX:510});c.events.get('pointerup')({...pointer,clientX:510});assert.equal(c.moved,true);assert.equal(c.scheduled,5000);cases.push('clip clicks seek while clip drags keep editing behavior');
 c.waStopSources=()=>{};c.trackPlaybacks=[];c.waMasterBus=null;c.masterPlaybackGainNode=null;c.waBuildMasterGraph=()=>{};c.playbackToken=0;c.current.master_inserts=[];c.MtaPlaybackPrep.mapLimit=()=>{};c.waPrepUpdate=()=>{};c.waPreparation=null;c.waCreateTrackGraph=()=>({});c.startVuMeterLoop=()=>{};c.movePlayhead=()=>{};c.playRaf=null;
 const decoding=deferred();c.prepareTimelinePlaybackBuffers=()=>decoding.promise;
 vm.runInContext(part(source,'async function startWebAudioProjectPlayback(','function updatePlaybackGains(){'),c);
 const prep=c.startWebAudioProjectPlayback(false,1000);await settle();c.goToTimestamp(21000);decoding.resolve({tracks:[],buffers:[]});await prep;assert.equal(c.scheduled,21000);cases.push('manual position during WebAudio decode wins over captured start');
}
(async()=>{await ({native,server,web}[mode])();console.log(JSON.stringify({mode,cases}))})().catch(e=>{console.error(e);process.exitCode=1});
