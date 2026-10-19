/* Continuous source-domain PPQ for hardware MIDI Clock, matching the host map. */
(()=>{'use strict';
class TempoMap{
 constructor(p){const ratio=Math.max(.25,Math.min(4,p.bpm/(p.base_bpm||p.bpm))),bpm=(p.metronome_bpm||p.bpm)/ratio,signature=p.metronome_time_signature||p.time_signature||'4/4';let origin=(p.metronome_grid_origin_ms||0)+(p.metronome_shift_ms||0),points=[{at:0,bpm,signature,rephase:false}];
 if(p.metronome_mode==='zones'){const boundaries=[{at:0,id:'START'},...(p.markers||[]).filter(m=>!m.disabled&&!m.deleted&&m.time_ms>0).sort((a,b)=>a.time_ms-b.time_ms).map(m=>({at:m.time_ms,id:m.id})),{at:86400000,id:'END'}];points=[];for(let i=0;i<boundaries.length-1;i++){const left=boundaries[i],right=boundaries[i+1],key=left.id+'|'+right.id;const manual=(name,fallback)=>{const values=p[name]||{};if(Object.hasOwn(values,key))return values[key];const match=Object.entries(values).filter(([k])=>k.split('|')[0]===left.id||k.split('|').at(-1)===right.id).map(([,v])=>v);return match.length===1?match[0]:fallback};points.push({at:left.at,bpm:manual('metronome_manual_zone_bpms',p.metronome_zone_bpms?.[left.at]??bpm*ratio)/ratio,signature:manual('metronome_manual_zone_signatures',p.metronome_zone_signatures?.[left.at]||signature),rephase:true})}origin=0}
 else if(p.metronome_mode==='adaptive'&&p.adaptive_tempo_map?.length){const raw=[...p.adaptive_tempo_map].sort((a,b)=>a.time_ms-b.time_ms);points=raw.map((v,i)=>{const next=raw[i+1],dt=next?next.time_ms-v.time_ms:0,beats=next?next.beat_index-v.beat_index:0;return{at:v.time_ms,bpm:(dt>0&&beats>0?60000*beats/dt:v.bpm)/ratio,signature:p.time_signature||'4/4'}});origin=points[0].at}
 let ppq=0,bar=0,previous=null;this.points=[];for(const piece of points){const [n,d]=piece.signature.split('/').map(Number);if(!previous){ppq=(piece.at-origin)*piece.bpm/60000;bar=Math.floor(ppq/(n*4/d))*(n*4/d)}else ppq+=(piece.at-previous.at)*previous.bpm/60000;if(piece.rephase||(previous&&piece.signature!==previous.signature))bar=ppq;const item={...piece,ppq,bar,n,d};if(this.points.at(-1)?.at===piece.at)this.points.pop();this.points.push(item);previous=item}
 }
 ppq(ms){let p=this.points[0];for(const v of this.points){if(v.at>ms)break;p=v}return p.ppq+(ms-p.at)*p.bpm/60000}
 time(ppq){let p=this.points[0];for(const v of this.points){if(v.ppq>ppq)break;p=v}return p.at+(ppq-p.ppq)*60000/p.bpm}
}
window.MtaTempoMap=TempoMap;
})();
