/* Real sample stream contract: bit-exact FIFO and time-correct resampling. */
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
function render(sourceRate,outputRate,signal){
 let Processor;const messages=[],context={Float32Array,Math,sampleRate:outputRate,currentTime:0,
 AudioWorkletProcessor:class{constructor(){this.port={postMessage:m=>messages.push(m)}}},registerProcessor:(name,p)=>Processor=p};
 vm.createContext(context);vm.runInContext(fs.readFileSync('app/static/server_pcm_worklet.js','utf8'),context);
 const sink=new Processor();sink.reset({generation:1,frame:0,rate:sourceRate,paused:false,threshold:128});
 const frames=sourceRate*2,pcm=new Float32Array(frames*2);for(let i=0;i<frames;i++){pcm[i*2]=signal(i);pcm[i*2+1]=-signal(i)}
 // Split at non-quantum boundaries. No samples may disappear between packets.
 let at=0;for(const n of [4093,8191,16381,frames]){const count=Math.min(n,frames-at);if(!count)break;const part=pcm.slice(at*2,(at+count)*2);sink.message({type:'pcm',generation:1,frame:at,frames:count,buffer:part.buffer,ended:at+count===frames,meters:{}});at+=count}
 const actual=[];let ended=false;
 for(let i=0;i<outputRate*3/128;i++){
  const left=new Float32Array(128),right=new Float32Array(128);sink.process([],[ [left,right] ]);actual.push(...left);context.currentTime+=128/outputRate;
  if(sink.ended){ended=true;break}
 }
 assert(ended);assert.equal(sink.frame,frames);assert.equal(sink.underruns,0);assert(Math.abs(actual.length-outputRate*2)<256);
 return {actual:actual.slice(0,Math.round(outputRate*2)),pcm};
}
let result=render(48000,48000,i=>Math.sin(i*.051)*.2);
for(let i=0;i<result.actual.length;i++)assert.equal(result.actual[i],result.pcm[i*2],`FIFO changed sample ${i}`);
for(const [source,output] of [[44100,48000],[48000,44100],[96000,48000]]){
 result=render(source,output,()=>.25);for(let i=100;i<result.actual.length-100;i++)assert(Math.abs(result.actual[i]-.25)<1e-5,'Resampler gain/time drift');
}
result=render(96000,48000,i=>Math.sin(2*Math.PI*30000*i/96000)*.2);
const rms=Math.sqrt(result.actual.slice(100,-100).reduce((n,x)=>n+x*x,0)/(result.actual.length-200));assert(rms<.001,'Downsampling must reject out-of-band aliasing');
console.log('Continuous PCM: bit-exact packet boundaries, EOF, source clock, 44.1/48/96 kHz and anti-aliasing passed');
