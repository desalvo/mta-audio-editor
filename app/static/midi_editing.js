/* Deterministic musical editing. Transformations operate on copies and are undoable. */
(function(root,factory){const api=factory();if(typeof module==='object')module.exports=api;else root.MtaMidiEditing=api})(globalThis,()=>{'use strict';
const clone=x=>JSON.parse(JSON.stringify(x)),clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
function nearestGrid(value,step,swing=0){
 if(![value,step,swing].every(Number.isFinite)||step<=0||Math.abs(swing)>.49)throw Error('Invalid MIDI grid');
 const center=Math.floor(value/step);let target=0,distance=Infinity;
 for(let i=center-2;i<=center+2;i++){const at=(i+(i%2?swing:0))*step,d=Math.abs(at-value);if(d<=distance){target=at;distance=d}}
 return target;
}
function projectGridTarget(note,track,clock,subdivisions=4,swing=0){
 if(!Number.isFinite(subdivisions)||subdivisions<=0)throw Error('Invalid MIDI subdivision');
 // Source edits affect every repeated clip; use the first audible occurrence as reference.
 const clip=(track.clips||[]).find(c=>note.start_ms>=c.source_start_ms&&note.start_ms<c.source_end_ms);
 const offset=Number(track.delay_ms||0)+(clip?clip.timeline_start_ms-clip.source_start_ms:0);
 const at=note.start_ms+offset,q=clock.quarterAt(at);
 const anchors=clock.anchors||[{at:clock.origin||0,q:0}];
 let index=0;for(let i=1;i<anchors.length&&anchors[i].at<=at;i++)index=i;
 const anchor=anchors[index],next=anchors[index+1];
 const snapped=clock.timeAtQuarter(anchor.q+nearestGrid(q-anchor.q,1/subdivisions,swing));
 const candidates=[next?Math.min(snapped,next.at):snapped,anchor.at];
 if(next)candidates.push(next.at);
 const target=candidates.reduce((best,value)=>Math.abs(value-at)<Math.abs(best-at)?value:best);
 return target-offset;
}
function transform(notes,ids,action,options={}){
 const result=clone(notes),chosen=result.filter(n=>ids.has(n.id));if(!chosen.length)return result;
 const step=Number(options.step||125),value=Number(options.value||0),strength=clamp(Number(options.strength??1),0,1),swing=clamp(Number(options.swing||0),-.49,.49);
 if(!Number.isFinite(step)||step<=0||![value,strength,swing].every(Number.isFinite))throw Error('Invalid MIDI transform parameters');
 if(!Number.isFinite(Number(options.seed??1))||!Number.isFinite(Number(options.velocity??5)))throw Error('Invalid humanization parameters');
 let seed=(Number(options.seed??1)>>>0)||1;const random=()=>{seed^=seed<<13;seed^=seed>>>17;seed^=seed<<5;return (seed>>>0)/4294967296};
 if(action==='move'){
  const delta=clamp(value,-Math.min(...chosen.map(n=>n.start_ms)),86400000-Math.max(...chosen.map(n=>n.start_ms+n.duration_ms)));
  for(const n of chosen)n.start_ms+=delta;
 }else if(action==='transpose'){
  const delta=clamp(Math.round(value),-Math.min(...chosen.map(n=>n.pitch)),127-Math.max(...chosen.map(n=>n.pitch)));
  for(const n of chosen)n.pitch+=delta;
 }else if(action==='quantize')for(const n of chosen){const target=options.quantizeTarget?options.quantizeTarget(n):nearestGrid(n.start_ms,step,swing);if(!Number.isFinite(target))throw Error('Invalid MIDI quantization target');const start=clamp(n.start_ms+(target-n.start_ms)*strength,0,86400000-n.duration_ms);if(start!==n.start_ms){n.start_ms=start;n.origin='manual';n.confidence=null;n.confidence_metric=''}}
 else if(action==='humanize')for(const n of chosen){n.start_ms=clamp(n.start_ms+(random()*2-1)*Math.abs(value),0,86400000-n.duration_ms);n.velocity=clamp(Math.round(n.velocity+(random()*2-1)*Number(options.velocity??5)),1,127)}
 else if(action==='velocity')for(const n of chosen)n.velocity=clamp(Math.round(value),1,127);
 else if(action==='duration')for(const n of chosen)n.duration_ms=clamp(value,.01,86400000-n.start_ms);
 else if(action==='scale'){if(value<=0||value>16)throw Error('Time scale must be >0 and <=16');const origin=Math.min(...chosen.map(n=>n.start_ms));for(const n of chosen){n.start_ms=origin+(n.start_ms-origin)*value;n.duration_ms*=value;if(n.start_ms+n.duration_ms>86400000)throw Error('MIDI duration exceeds 24 hours')}}
 else if(action==='split'){const additions=[];for(const n of chosen){if(value>n.start_ms&&value<n.start_ms+n.duration_ms){additions.push({...n,id:options.uid(),start_ms:value,duration_ms:n.start_ms+n.duration_ms-value});n.duration_ms=value-n.start_ms}}result.push(...additions)}
 else if(action==='join'){const groups=new Map();for(const n of chosen){const key=n.channel+':'+n.pitch;if(!groups.has(key))groups.set(key,[]);groups.get(key).push(n)}const removed=new Set();for(const group of groups.values()){group.sort((a,b)=>a.start_ms-b.start_ms);const first=group[0];first.duration_ms=Math.max(...group.map(n=>n.start_ms+n.duration_ms))-first.start_ms;for(const n of group.slice(1))removed.add(n.id)}return result.filter(n=>!removed.has(n.id))}
 else throw Error('Unknown MIDI transformation');
 return result;
}
return{transform,clone,nearestGrid,projectGridTarget};
});
