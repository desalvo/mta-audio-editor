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
root.MtaPlaybackPrep={mapLimit,clipPlan,BufferCache};
})(typeof window==='undefined'?globalThis:window);
