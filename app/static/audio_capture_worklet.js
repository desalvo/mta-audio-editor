class MtaAudioCapture extends AudioWorkletProcessor{
 constructor(){super();this.buffers=[new Float32Array(4096),new Float32Array(4096)];this.position=0;this.port.onmessage=e=>{if(e.data==='flush'){const packet=new Float32Array(this.position*2);for(let i=0;i<this.position;i++){packet[i*2]=this.buffers[0][i];packet[i*2+1]=this.buffers[1][i]}if(packet.length)this.port.postMessage(packet.buffer,[packet.buffer]);this.position=0;this.port.postMessage('flushed')}}}
 process(inputs){const channels=inputs[0];if(!channels?.length)return true;const n=channels[0].length;
 for(let i=0;i<n;i++){this.buffers[0][this.position]=channels[0][i];this.buffers[1][this.position]=channels[1]?.[i]??channels[0][i];if(++this.position===4096){const packet=new Float32Array(8192);for(let j=0;j<4096;j++){packet[j*2]=this.buffers[0][j];packet[j*2+1]=this.buffers[1][j]}this.port.postMessage(packet.buffer,[packet.buffer]);this.position=0}}
 return true}
}
registerProcessor('mta-audio-capture',MtaAudioCapture);
