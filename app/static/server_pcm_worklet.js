/* Continuous bounded PCM sink. Fetch/validation run in a dedicated Worker. */
class MtaServerPcm extends AudioWorkletProcessor{
 constructor(){super();this.capacity=262144;this.left=new Float32Array(this.capacity);this.right=new Float32Array(this.capacity);this.worker=null;this.generation=-1;this.reset({generation:0,frame:0,paused:true});this.port.onmessage=e=>{if(e.data.type==='attach'){this.worker=e.data.port;this.worker.onmessage=m=>this.message(m.data);this.worker.start()}else this.message(e.data)}}
 reset(m){this.token=m.token||null;this.generation=m.generation;this.frame=m.frame;this.step=(m.rate||sampleRate)/sampleRate;this.fraction=0;this.coefficients=null;this.prepareResampler();for(let i=this.capacity-64;i<this.capacity;i++){this.left[i]=0;this.right[i]=0};this.readAt=0;this.writeAt=0;this.queued=0;this.played=0;this.descriptors=[];this.started=false;this.paused=!!m.paused;this.ended=false;this.eof=false;this.meters={};this.threshold=m.threshold||Math.round((m.rate||sampleRate)*.35);this.underruns=0;this.status();if(m.token)this.port.postMessage({type:'reset-ready',generation:this.generation,token:this.token})}
 prepareResampler(){
  if(Math.abs(this.step-1)<1e-12)return;
  this.coefficients=new Float32Array(1024*64);const cutoff=Math.min(1,1/this.step)*.95;
  for(let phase=0;phase<1024;phase++){
   const fraction=phase/1024;let sum=0;
   for(let tap=0;tap<64;tap++){const x=tap-31-fraction,y=Math.PI*x*cutoff,v=(Math.abs(y)<1e-9?1:Math.sin(y)/y)*cutoff*(.42+.5*Math.cos(Math.PI*x/32)+.08*Math.cos(2*Math.PI*x/32));this.coefficients[phase*64+tap]=v;sum+=v}
   for(let tap=0;tap<64;tap++)this.coefficients[phase*64+tap]/=sum;
  }
 }
 status(){this.port.postMessage({type:'status',token:this.token,generation:this.generation,frame:this.frame,contextTime:currentTime,queued:this.queued,buffering:!this.started&&!this.paused&&!this.ended,ended:this.ended,underruns:this.underruns,meters:this.meters})}
 message(m){
  if(m.type==='reset'){this.reset(m);return}
  if(m.generation!==this.generation)return;
  if(m.type==='pcm'){
   const data=new Float32Array(m.buffer);if(m.frames*2!==data.length||this.queued+m.frames>this.capacity){this.port.postMessage({type:'error',message:'Invalid or overflowing audio queue'});this.paused=true;return}
   for(let i=0;i<m.frames;i++){this.left[this.writeAt]=data[i*2];this.right[this.writeAt]=data[i*2+1];this.writeAt=(this.writeAt+1)%this.capacity}
   this.queued+=m.frames;this.descriptors.push({end:m.frame+m.frames,meters:m.meters});this.eof=!!m.ended;
   if(this.queued>=this.threshold||this.eof){this.started=true;this.paused=false}
   return;
  }
  if(m.type==='eof'){this.eof=true;if(this.queued)this.started=true;else{this.ended=true;this.meters={};this.status()}return}
 }
 process(inputs,outputs){
  const out=outputs[0];if(!out||out.length<2)return true;const count=out[0].length;
  if(this.paused||!this.started){this.statusCounter=(this.statusCounter||0)+count;if(this.statusCounter>=2048){this.statusCounter=0;this.status()}return true}
  let consumed=0;
  for(let i=0;i<count;i++){
   if(this.queued<(this.coefficients?33+Math.ceil(this.step):1)&&!this.eof||!this.queued){
    if(this.eof){this.ended=true;this.started=false;this.meters={}}
    else{this.underruns++;this.started=false;this.meters={};this.worker?.postMessage({type:'underrun',generation:this.generation})}
    break;
   }
   if(this.coefficients){
    let l=0,r=0;const phase=Math.min(1023,Math.floor(this.fraction*1024))*64;
    for(let tap=0;tap<64;tap++){const offset=tap-31;if(offset>=this.queued)continue;const at=(this.readAt+offset+this.capacity)%this.capacity,c=this.coefficients[phase+tap];l+=this.left[at]*c;r+=this.right[at]*c}
    out[0][i]=l;out[1][i]=r;
   }else{out[0][i]=this.left[this.readAt];out[1][i]=this.right[this.readAt]}
   this.fraction+=this.step;const advance=Math.min(this.queued,Math.floor(this.fraction));this.fraction-=advance;this.readAt=(this.readAt+advance)%this.capacity;this.queued-=advance;this.frame+=advance;consumed+=advance;
   while(this.descriptors.length&&this.frame>this.descriptors[0].end)this.descriptors.shift();
   if(this.descriptors.length)this.meters=this.descriptors[0].meters;
  }
  this.played+=consumed;
  if(this.played>=2048||!this.started){this.worker?.postMessage({type:'consumed',generation:this.generation,frames:this.played});this.played=0;this.status()}
  return true;
 }
}
registerProcessor('mta-server-pcm',MtaServerPcm);
