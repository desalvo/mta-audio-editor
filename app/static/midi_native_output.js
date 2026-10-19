/* Serialize bridge writes: a late note-on must never overtake Panic. */
(function(root){'use strict';
function create(name,bridge,onError,now=()=>performance.now()){
 let chain=Promise.resolve(),epoch=0,pending=0,panicPending=false;
 const report=error=>{onError?.(error);};
 const port={id:name,name,native:true,
  send(data,stamp){
   if(pending>=4096){port.clear();throw Error('MIDI output queue full: voices stopped')}
   const generation=epoch,target=stamp||now(),message=[...data];pending++;
   chain=chain.then(()=>generation===epoch?bridge.midi_send(name,message,Math.max(0,Math.min(1000,target-now()))):undefined).catch(report).finally(()=>pending--);
  },
  clear(){epoch++;if(!panicPending){panicPending=true;chain=chain.then(()=>bridge.midi_panic(name)).catch(report).finally(()=>{panicPending=false})}return chain},
  idle(){return chain}
 };return port;
}
const api={create};if(typeof module!=='undefined')module.exports=api;root.MtaNativeMidiOutput=api;
})(typeof window==='undefined'?globalThis:window);
