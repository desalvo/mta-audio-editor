/* Shared bounded preparation and sample-accurate dry timeline scheduling. */
(function(root){'use strict';
async function mapLimit(items,limit,task){const result=new Array(items.length);let next=0;await Promise.all(Array.from({length:Math.min(limit,items.length)},async()=>{while(next<items.length){const i=next++;result[i]=await task(items[i],i)}}));return result}
function clipPlan(track,bufferDuration,cursorSeconds){
 const clips=track.clips?.length?track.clips:track.clips_initialized?[]:[{timeline_start_ms:0,source_start_ms:0,source_end_ms:bufferDuration*1000}];
 return clips.flatMap(c=>{const start=(Number(c.timeline_start_ms||0)+Number(track.delay_ms||0))/1000,source=Number(c.source_start_ms||0)/1000,end=Math.min(Number(c.source_end_ms||0)/1000,bufferDuration),skip=Math.max(0,cursorSeconds-start),duration=end-source-skip;if(duration<=0)return [];return [{when:Math.max(0,start-cursorSeconds),offset:source+skip,duration}]});
}
class BufferCache{
 constructor(maxBytes=256*1024*1024){this.maxBytes=maxBytes;this.ready=new Map();this.pending=new Map();this.bytes=0}
 async get(key,load){if(this.ready.has(key)){const b=this.ready.get(key);this.ready.delete(key);this.ready.set(key,b);return b}if(this.pending.has(key))return this.pending.get(key);const work=Promise.resolve().then(load).then(buffer=>{const bytes=buffer.length*buffer.numberOfChannels*4;if(bytes<=this.maxBytes){while(this.bytes+bytes>this.maxBytes&&this.ready.size)this.delete(this.ready.keys().next().value);this.ready.set(key,buffer);this.bytes+=bytes}return buffer}).finally(()=>this.pending.delete(key));this.pending.set(key,work);return work}
 delete(key){const b=this.ready.get(key);if(b){this.bytes-=b.length*b.numberOfChannels*4;this.ready.delete(key)}}
 clear(){this.ready.clear();this.bytes=0}
 keys(){return this.ready.keys()}
}
// Audio preparation owns a separate surface: never replace an open editor.
let progressOwner=null,progressView=null;
function hideProgress(owner){
 if(owner!==undefined&&owner!==progressOwner)return;
 progressView?.remove();progressView=null;progressOwner=null;
}
function showProgress(owner,title,pct,message,detail=''){
 if(!root.document)return;
 if(!progressView){
  const view=root.document.createElement('section');view.id='audioPreparation';view.className='audio-preparation';
  const heading=root.document.createElement('strong'),bar=root.document.createElement('progress'),phase=root.document.createElement('p'),info=root.document.createElement('small'),stop=root.document.createElement('button');
  heading.id='audioPreparationTitle';view.setAttribute('aria-labelledby',heading.id);view.setAttribute('role','region');phase.setAttribute('role','status');bar.max=100;stop.type='button';stop.textContent=typeof root.tr==='function'?root.tr('Stop','Interrompi'):'Stop';
  stop.onclick=()=>{hideProgress();root.stopPlayback?.()};view.append(heading,bar,phase,info,stop);root.document.body.append(view);progressView=view;
 }
 progressOwner=owner;const [heading,bar,phase,info]=progressView.children;heading.textContent=title;phase.textContent=message||'';info.textContent=detail;
 if(Number.isFinite(pct)&&pct>=0)bar.value=Math.min(100,pct);else bar.removeAttribute('value');
}
function mixerControls(project){return {master_volume_db:project.master_volume_db||0,tracks:project.tracks.map(t=>({id:t.id,gain_db:t.gain_db||0,volume_db:t.volume_db||0,pan:t.pan||0,mute:!!t.mute,solo:!!t.solo}))}}
function paintMeters(project,meters,silent=false){
 const level=v=>Math.max(0,Math.min(100,(20*Math.log10(Math.max(1e-9,Number(v)||0))+60)/60*100));
 function route(id,values){
  values=silent?[0,0,0,0]:(values||[0,0,0,0]);
  for(const [channel,value] of [['L',values[0]],['R',values[1]],['M',Math.max(values[0],values[1])]]){const el=root.document.getElementById('vu-'+id+'-'+channel);if(el)el.style.height=level(value)+'%'}
  if(!silent&&Math.max(values[2],values[3])>=1)root.document.getElementById('peak-'+id)?.classList.add('active');
 }
 route('master',meters?.master);project?.tracks?.forEach((t,i)=>route(t.id,meters?.tracks?.[i]));
}
function transportButton(state){
 const button=root.document?.getElementById('playMaster');if(!button)return;
 const playing=state==='playing',label=typeof root.tr==='function'?root.tr(playing?'Pause':state==='paused'?'Resume':'Play',playing?'Pausa':state==='paused'?'Riprendi':'Riproduci'):(playing?'Pause':'Play');
 button.dataset.playbackState=state;button.title=label;button.setAttribute('aria-label',label);button.replaceChildren();
 const svg=root.document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('width','20');svg.setAttribute('height','20');svg.setAttribute('aria-hidden','true');
 if(playing){for(const x of [6,14]){const bar=root.document.createElementNS(svg.namespaceURI,'rect');for(const [k,v] of Object.entries({x,y:4,width:4,height:16,rx:1,fill:'currentColor'}))bar.setAttribute(k,String(v));svg.append(bar)}}
 else{const path=root.document.createElementNS(svg.namespaceURI,'path');path.setAttribute('d','M7 4v16l14-8z');path.setAttribute('fill','currentColor');svg.append(path)}
 button.append(svg);
}
root.MtaPlaybackPrep={transportButton,mixerControls,paintMeters,mapLimit,clipPlan,BufferCache,showProgress,hideProgress};
})(typeof window==='undefined'?globalThis:window);
