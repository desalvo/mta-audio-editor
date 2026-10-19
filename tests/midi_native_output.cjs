'use strict';
const assert=require('node:assert/strict');
const {create}=require('../app/static/midi_native_output.js');
(async()=>{
 let finish;const writes=[],errors=[];
 const bridge={midi_send:async(name,data)=>{writes.push(data);if(data[1]===60)await new Promise(resolve=>finish=resolve)},midi_panic:async()=>writes.push('panic')};
 const port=create('Test output',bridge,error=>errors.push(error),()=>0);
 port.send([144,60,100]);await new Promise(resolve=>setImmediate(resolve));
 port.send([144,61,100]);port.clear();port.send([144,62,100]);finish();await port.idle();
 assert.deepEqual(writes,[[144,60,100],'panic',[144,62,100]]);
 assert.deepEqual(errors,[]);
 const limited=create('Limited', {midi_send:async()=>{},midi_panic:async()=>{}},error=>errors.push(error),()=>0);
 for(let i=0;i<4096;i++)limited.send([144,60,100]);
 assert.throws(()=>limited.send([144,60,100]),/queue full/);
 for(let i=0;i<100;i++)limited.clear();
 await limited.idle();assert.deepEqual(errors,[]);
 console.log('Native MIDI bridge: ordering, Panic, cancellation and bounded queue OK');
})().catch(error=>{console.error(error);process.exitCode=1});
