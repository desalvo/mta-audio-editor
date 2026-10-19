/* MIDI 1.0 clip mapping and chase shared by browser hardware scheduling tests. */
(function(root){'use strict';
function chase(events,at){const controls=new Map(),held=new Map(),sustained=new Map(),pedal=new Map();
 for(const e of [...events].sort((a,b)=>a.at-b.at)){if(e.at>=at)break;const m=e.data;if(m[0]>=240)continue;const k=m[0]&240,ch=m[0]&15,key=ch+':'+m[1];
  if(k===144&&m[2]){held.set(key,m);sustained.delete(key)}
  else if(k===128||(k===144&&!m[2])){const note=held.get(key);held.delete(key);if(pedal.get(ch)&&note)sustained.set(key,note)}
  else{controls.set(ch+':'+k+':'+([176,160].includes(k)?m[1]:0),m);if(k===176){if(m[1]===64){pedal.set(ch,m[2]>=64);if(m[2]<64)for(const key of sustained.keys())if(key.startsWith(ch+':'))sustained.delete(key)}else if([120,123].includes(m[1])){for(const map of [held,sustained])for(const key of map.keys())if(key.startsWith(ch+':'))map.delete(key)}}}
 }
 const result=[...controls.values(),...held.values()];for(const [key,m] of sustained)result.push(m,[128|(m[0]&15),m[1],0]);return result;
}
function events(track){const raw=[],channels=new Map();let active=[];const zone=track.mpe_zone||'off',members=track.mpe_members||15,bend=track.mpe_pitch_bend||48;const pool=Array.from({length:members},(_,i)=>zone==='upper'?15-members+i:i+1);
 if(zone!=='off'){const master=zone==='upper'?15:0;for(const [cc,value] of [[101,0],[100,6],[6,members],[101,127],[100,127]])raw.push({at:0,data:[176|master,cc,value]});for(const ch of pool)for(const [cc,value] of [[101,0],[100,0],[6,bend],[38,0],[101,127],[100,127]])raw.push({at:0,data:[176|ch,cc,value]})}
 for(const n of [...(track.midi_notes||[])].sort((a,b)=>a.start_ms-b.start_ms)){let ch=n.channel||0;if(zone!=='off'&&(ch===0||ch===15)){active=active.filter(a=>a.end>n.start_ms);ch=pool.find(c=>!active.some(a=>a.channel===c));if(ch===undefined)throw Error('MPE polyphony exceeds member channels');active.push({end:n.start_ms+n.duration_ms,channel:ch})}channels.set(n.id,ch)}
 for(const n of track.midi_notes||[]){const ch=channels.get(n.id);raw.push({at:n.start_ms,data:[144|ch,n.pitch,n.velocity]},{at:n.start_ms+n.duration_ms,data:[128|ch,n.pitch,0]})}for(const e of track.midi_sysex||[])raw.push({at:e.time_ms,data:e.data});for(const c of track.midi_controls||[])raw.push({at:c.time_ms,data:c.data});const out=[];
 const clips=track.clips?.length?track.clips:track.clips_initialized?[]:[{source_start_ms:0,source_end_ms:track.duration_ms,timeline_start_ms:0}];
 for(const c of clips){const offset=c.timeline_start_ms+(track.delay_ms||0),length=c.source_end_ms-c.source_start_ms;for(const data of chase(raw,c.source_start_ms))out.push({at:offset,data});for(const e of raw)if(e.at>=c.source_start_ms&&e.at<c.source_end_ms)out.push({at:offset+e.at-c.source_start_ms,data:e.data});for(const ch of new Set(raw.map(e=>e.data[0]&15)))out.push({at:offset+length,data:[176|ch,64,0]},{at:offset+length,data:[176|ch,123,0]});if(out.length>150000)throw Error('MIDI clip event limit exceeded')}
 return out.sort((a,b)=>a.at-b.at||((a.data[0]&240)===128?0:1)-((b.data[0]&240)===128?0:1));
}
function lowerBound(events,at){let lo=0,hi=events.length;while(lo<hi){const mid=(lo+hi)>>>1;if(events[mid].at<at)lo=mid+1;else hi=mid}return lo}
const api={events,chase,lowerBound};if(typeof module!=='undefined')module.exports=api;root.MtaMidiRules=api;
})(typeof window==='undefined'?globalThis:window);
