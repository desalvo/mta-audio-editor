/* Timeline math shared by pointer/keyboard gestures and regression tests. */
(function(root){
 const key=(t,c)=>`${t.id}:${c.id}`,length=c=>Math.max(0,c.source_end_ms-c.source_start_ms),start=(t,c)=>Number(c.timeline_start_ms||0)+Number(t.delay_ms||0);
 function duration(p){return Math.max(0,Number(p.timeline_end_ms||0),...(p.tracks||[]).map(t=>(t.clips?.length?Math.max(...t.clips.map(c=>start(t,c)+length(c))):t.clips_initialized?0:Number(t.duration_ms||0))))}
 function manual(values,left,right){const k=`${left}|${right}`;if(values?.[k]!=null)return values[k];const hits=Object.entries(values||{}).filter(([k])=>k.split('|')[0]===left||k.split('|').at(-1)===right);return hits.length===1?hits[0][1]:null}
 function gridAt(p,ms=0){
  let bpm=Number(p.metronome_bpm||p.bpm||120),signature=p.metronome_time_signature||p.time_signature||'4/4',origin=Number(p.metronome_grid_origin_ms||0)+Number(p.metronome_shift_ms||0),end=Infinity,left='START',right='END';
  if(p.metronome_mode==='adaptive'){
   const points=(p.adaptive_tempo_map||[]).filter(x=>Number(x.time_ms)+Number(p.metronome_shift_ms||0)<=ms);bpm=Number(points.at(-1)?.bpm||p.bpm||120);signature=p.time_signature||'4/4';
  }else if(p.metronome_mode==='zones'){
   const marks=(p.markers||[]).filter(m=>!m.deleted&&!m.disabled&&m.time_ms>0&&m.time_ms<duration(p)).sort((a,b)=>a.time_ms-b.time_ms);
   const points=[{id:'START',time_ms:0},...marks,{id:'END',time_ms:Math.max(duration(p),ms+1)}];
   const i=Math.max(0,points.findIndex((x,i)=>i<points.length-1&&ms>=x.time_ms&&ms<points[i+1].time_ms));origin=points[i].time_ms;end=points[i+1].time_ms;left=points[i].id;right=points[i+1].id;
   bpm=Number(manual(p.metronome_manual_zone_bpms,left,right)??p.metronome_zone_bpms?.[String(origin)]??bpm);
   signature=manual(p.metronome_manual_zone_signatures,left,right)??p.metronome_zone_signatures?.[String(origin)]??signature;
   origin=ms<Number(p.metronome_insertion_ms||0)&&p.metronome_pre_roll_bars?Number(p.metronome_start_ms||0):Math.max(origin,Number(p.metronome_insertion_ms||p.metronome_start_ms||0));
  }
  return {bpm,signature,origin,end,left,right,beats:Number(signature.split('/')[0])||4};
 }
 function step(p,ms=0){const g=gridAt(p,ms);return 60000/Math.max(1,g.bpm)*(p.timeline_snap==='bars'?g.beats:1)}

 function delta(p,keys,wanted,px=70,anchor=null){
  const moving=[],other=[];for(const t of p.tracks||[])for(const c of t.clips||[])if(length(c)>0)(keys.has(key(t,c))?moving:other).push({t,c,s:start(t,c),n:length(c)});
  if(!moving.length)return 0;
  let lo=Math.max(...moving.map(x=>-Number(x.c.timeline_start_ms||0))),hi=Infinity;
  for(const a of moving)for(const b of other)if(a.t.id===b.t.id){if(b.s+b.n<=a.s)lo=Math.max(lo,b.s+b.n-a.s);else if(b.s>=a.s+a.n)hi=Math.min(hi,b.s-a.s-a.n);else return 0}
  if(lo>hi)return 0;
  let d=Math.max(lo,Math.min(hi,Math.round(wanted)));
  if(p.timeline_magnetic){let best=null;const tolerance=8000/Math.max(.01,px);for(const a of moving)for(const b of other)for(const edge of [a.s,a.s+a.n])for(const target of [b.s,b.s+b.n]){const n=Math.round(target-edge);if(n>=lo&&n<=hi&&Math.abs(n-d)<=tolerance&&(best===null||Math.abs(n-d)<Math.abs(best-d)))best=n}if(best!==null)return best}
  if(p.timeline_snap&&p.timeline_snap!=='off'){
   const a=moving.find(x=>key(x.t,x.c)===anchor)||moving[0],desired=a.s+d,g=gridAt(p,desired),origin=g.origin,unit=step(p,desired);
   const points=(p.metronome_mode==='adaptive'?(p.adaptive_tempo_map||[]):[]).filter((x,i)=>p.timeline_snap!=='bars'||i%Number((p.time_signature||'4/4').split('/')[0])===0).map(x=>Number(x.time_ms)+Number(p.metronome_shift_ms||0));
   const candidates=points.length&&desired>=points[0]&&desired<=points[points.length-1]?points:[origin+Math.floor((desired-origin)/unit)*unit,origin+Math.ceil((desired-origin)/unit)*unit];
   const valid=candidates.map(x=>Math.round(x-a.s)).filter(x=>x>=lo&&x<=hi);if(!valid.length)return 0;d=valid.reduce((a,b)=>Math.abs(b-d)<Math.abs(a-d)?b:a);
  }
  return d;
 }
 function fade(p,ms){if(!p.master_fade_enabled)return 1;const end=duration(p),clamp=v=>Math.max(0,Math.min(1,v));return (p.master_fade_in_ms?clamp(ms/p.master_fade_in_ms):1)*(p.master_fade_out_ms?clamp((end-ms)/p.master_fade_out_ms):1)}
 const api={key,length,start,duration,gridAt,step,delta,fade};if(typeof module!=='undefined')module.exports=api;root.MtaTimelineRules=api;
})(typeof globalThis!=='undefined'?globalThis:this);
