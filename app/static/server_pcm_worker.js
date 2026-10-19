/* Network and PCM validation are independent of GUI stalls/background timers. */
'use strict';let sink=null,state=null,inflight=null,pauseReplies=[];
function replyPause(){if(!inflight)for(const token of pauseReplies.splice(0))postMessage({type:'paused',token})}
function fail(error){if(state)state.running=false;postMessage({type:'error',message:error.message||String(error)});replyPause()}
function pump(){
 if(inflight||!state?.running||state.eof||state.queued>=state.target)return;
 const s=state;inflight=(async()=>{
  while(state===s&&s.running&&!s.eof&&s.queued<s.target){
   const began=performance.now();const r=await fetch(s.url+'/pcm',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-MTA-Request':'1'},body:JSON.stringify({sequence:s.sequence,frames:s.chunk}),cache:'no-store'});
   if(!r.ok){let text;try{text=(await r.json()).detail}catch{text=r.statusText}throw Error(text||'Server audio request failed')}
   const buffer=await r.arrayBuffer();if(state!==s||!s.running)break;
   const frames=Number(r.headers.get('X-MTA-Frames')),rate=Number(r.headers.get('X-MTA-Rate')),frame=Number(r.headers.get('X-MTA-Start-Frame')),sequence=Number(r.headers.get('X-MTA-Sequence'));
   if(!Number.isInteger(frames)||frames<0||frames>s.chunk||buffer.byteLength!==frames*8||rate!==s.rate||frame!==s.frame||sequence!==s.sequence+1)throw Error('Invalid server audio stream');
   const pcm=new DataView(buffer);for(let i=0;i<frames*2;i++)if(!Number.isFinite(pcm.getFloat32(i*4,true)))throw Error('Non-finite server audio');
   const meters=JSON.parse(r.headers.get('X-MTA-Meters')||'{}');
   s.sequence=sequence;s.frame+=frames;s.eof=r.headers.get('X-MTA-Ended')==='1'||!frames;
   const elapsed=(performance.now()-began)/1000;s.worst=Math.max(elapsed,s.worst*.98);s.target=Math.round(s.rate*Math.max(.35,Math.min(1.2,s.worst*3+.06)));
   s.chunk=Math.max(4096,Math.min(16384,2**Math.ceil(Math.log2(Math.max(1,s.worst*s.rate*2)))));
   if(frames){s.queued+=frames;sink.postMessage({type:'pcm',generation:s.generation,buffer,frames,frame,meters,ended:s.eof},[buffer])}
   else sink.postMessage({type:'eof',generation:s.generation});
  }
 })().catch(fail).finally(()=>{inflight=null;replyPause();if(state?.running&&state.queued<state.target&&!state.eof)pump()});
}
onmessage=e=>{
 const m=e.data;
 if(m.type==='attach'){
  sink=m.port;sink.onmessage=event=>{const v=event.data;if(v.generation!==state?.generation)return;if(v.type==='consumed')state.queued=Math.max(0,state.queued-v.frames);if(v.type==='underrun'){state.target=Math.min(state.rate*1.2,Math.max(state.target*1.5,state.rate*.6));state.worst=Math.max(state.worst,.18)}pump()};sink.start();return;
 }
 if(m.type==='pause'){if(state)state.running=false;pauseReplies.push(m.token);replyPause();return}
 if(m.type==='start'){
  state={url:m.url,rate:m.rate,frame:m.frame,sequence:m.sequence,generation:m.generation,queued:0,running:true,eof:false,target:Math.round(m.rate*.35),chunk:4096,worst:0};pump();
 }
};
