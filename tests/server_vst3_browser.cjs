/* Exercise the shipped browser adapter, including in-flight pulls and controls. */
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const wait=ms=>new Promise(r=>setTimeout(r,ms));
let fallbacks=0,persisted=0,position=0,sequence=0,engine='cpp',corrupt=false,delayRead=null,preparation=false;
const calls=[],nodes=[],messages=[];
const names=['previewMaster','stopPlayback','pausePlayback','resumePlayback','togglePlayback','playbackActuallyRunning','goToTimestamp','seekTransport','goTransportStart','timingAudioChanged','updatePlaybackGains','queueLiveFxRefresh'];
const window=Object.fromEntries(names.map(n=>[n,()=>{if(n==='previewMaster')fallbacks++}]));
window.addEventListener=()=>{};
class AudioContext{
 constructor(){this.currentTime=0;this.destination={}}
 async resume(){this.unlocked=true}
 createBuffer(ch,n,rate){const data=[new Float32Array(n),new Float32Array(n)];return{getChannelData:c=>data[c],data}}
 createBufferSource(){const node={connect(){},disconnect(){},stop(){this.stopped=true},start(at){this.at=at;nodes.push(this)}};return node}
}
window.AudioContext=AudioContext;
const button={};const context={window,console,setTimeout,clearTimeout,setInterval,clearInterval,performance,Promise,crypto:{randomUUID:()=> 'browser-client-0000001'},
 currentUser:{native_single_user:false},current:{id:'project',tracks:[{inserts:[{plugin:'vst3',enabled:true}]}],master_inserts:[]},audioCtx:null,playCursorMs:0,playbackPaused:false,timelineAudioDirty:false,
 tr:(en,it)=>en,toast:s=>messages.push(s),collect(){},async persistCurrentProject(){persisted++},$:()=>button,tempoRatio:()=>1,setPlayCursor(){},updateTimedPlaybackOverlay(){},setRenderPlaybackPreparing(){},requestAnimationFrame:()=>1,cancelAnimationFrame(){},
 api:async url=>{if(url==='/api/vst3/plugins'){assert(context.audioCtx?.unlocked,'Unlock WebAudio before awaiting server requests');return{engine,live_available:true,failed:false}}return{state:preparation?'preparing':'ready',failed:false}},
 fetch:async(url,options={})=>{
  const body=options.body?JSON.parse(options.body):{};calls.push([url,body,options.method]);
  if(url.endsWith('/vst3-live')){position=0;sequence=0;return{ok:true,json:async()=>({session_id:'session',rate:48000,position:0,position_ms:0,...(preparation?{state:'preparing'}:{})})}}
  if(url.endsWith('/control')){if(body.action==='seek'){position=Math.round(body.cursor_ms*48);sequence=0}return{ok:true,json:async()=>({status:{position,position_ms:position/48,ended:false}})}}
  if(url.endsWith('/pcm')){
   assert.equal(body.sequence,sequence);const frame=position;position+=body.frames;sequence++;
   const responseSequence=sequence;if(delayRead){const pending=delayRead;delayRead=null;await pending}
   const data=new Float32Array(body.frames*2);data.fill(.125);
   const headers={'X-MTA-Frames':String(body.frames),'X-MTA-Rate':'48000','X-MTA-Start-Frame':String(frame),'X-MTA-Sequence':String(corrupt?999:responseSequence),'X-MTA-Ended':'0'};
   return{ok:true,headers:{get:k=>headers[k]},arrayBuffer:async()=>data.buffer};
  }
  return{ok:true,json:async()=>({ok:true})};
 }};
vm.createContext(context);vm.runInContext(fs.readFileSync('app/static/server_vst3.js','utf8'),context);
(async()=>{
 await window.previewMaster();await wait(30);
 assert.equal(fallbacks,0);assert.equal(nodes.length,1);assert.equal(nodes[0].buffer.data[0][1],.125);assert(window.playbackActuallyRunning());
 context.audioCtx.currentTime=nodes[0].at+.1;
 await window.pausePlayback();
 assert(!window.playbackActuallyRunning());
 assert(Math.abs(calls.filter(c=>c[1].action==='seek').at(-1)[1].cursor_ms-100)<1e-8);
 const pullsBefore=calls.filter(c=>c[0].endsWith('/pcm')).length;await wait(40);
 assert.equal(calls.filter(c=>c[0].endsWith('/pcm')).length,pullsBefore);
 await window.resumePlayback();await wait(25);assert(window.playbackActuallyRunning());
 window.updatePlaybackGains();await wait(110);
 assert(calls.some(c=>c[1].action==='update'));assert(persisted>=2);
 // Pause while a pull is in flight: reset must wait for it before seeking.
 let release;delayRead=new Promise(r=>release=r);context.audioCtx.currentTime+=1;
 await wait(35);const paused=window.pausePlayback();await wait(10);
 const seeksBefore=calls.filter(c=>c[1].action==='seek').length;
 release();await paused;assert.equal(calls.filter(c=>c[1].action==='seek').length,seeksBefore+1);
 window.stopPlayback();assert(calls.some(c=>c[2]==='DELETE'));
 engine='current';await window.previewMaster();assert.equal(fallbacks,1);
 engine='cpp';corrupt=true;await window.previewMaster();await wait(30);
 assert(!window.playbackActuallyRunning());assert(messages.some(m=>m.includes('Invalid server audio stream')));assert.equal(fallbacks,1);
 window.stopPlayback();corrupt=false;preparation=true;
 const deletesBefore=calls.filter(c=>c[2]==='DELETE').length;
 const pending=window.previewMaster();await wait(20);window.stopPlayback();await pending;
 assert(calls.filter(c=>c[2]==='DELETE').length>deletesBefore);
 window.stopPlayback();console.log('Browser VST3 adapter: PCM, clock, pause/resume, in-flight seek, updates, teardown and fail-closed passed');
})().catch(e=>{window.stopPlayback();console.error(e);process.exitCode=1});
