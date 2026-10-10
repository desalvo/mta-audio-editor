"""Exercise real native PCM queue + MIDI event dispatcher coupling."""
import subprocess
from pathlib import Path


def test_native_event_audio_pump(tmp_path):
    root = Path(__file__).resolve().parents[1]
    source = tmp_path / "pump.cpp"
    source.write_text(r'''
#include "vst3_event_audio_pump.hpp"
#include <cassert>
using namespace mta;
struct Sink : EventSink {
 int count=0; bool reject=false;
 bool midi(const NativeMidiEvent&) noexcept override {++count;return !reject;}
 bool parameter(const NativeParameterEvent&) noexcept override {++count;return !reject;}
};
int main(){
 Vst3PlayoutBridge pcm(16,2,8,1); Vst3WorkerEvents events(16);
 assert(pcm.valid() && events.valid());
 Vst3EventAudioPump pump(pcm,events,1); Sink sink;
 auto processor=[](const float* in,float* out,std::size_t frames,std::size_t channels){
   for(std::size_t i=0;i<frames*channels;++i) {out[i]=in[i]*2;}
   return true;
 };
 float in[8]={1,2,3,4,5,6,7,8},out[8]{};
 Vst3EventPacket p; assert(p.initialize(1,0,8)); assert(p.note(2,0x90,64,100));
 assert(events.push(p)); assert(pcm.callback(in,out,8,1));
 assert(pump.pump_once(sink,processor)); assert(sink.count==1);
 assert(pcm.callback(in,out,8,1)); assert(pump.pump_once(sink,processor));
 assert(pcm.callback(in,out,8,1)); assert(out[0]==2 && out[7]==16);
 assert(pump.stats().processed==2 && pump.stats().silent_event_blocks==1);
 assert(pump.pump_once(sink,processor)); // process queued sequence 2
 // Rejected event delivery fails closed: no output from the processor.
 assert(p.initialize(1,3,8)); assert(p.parameter(5,0,0.5f)); assert(events.push(p));
 sink.reject=true; assert(pcm.callback(in,out,8,1));
 assert(pump.pump_once(sink,processor)); assert(pump.stats().rejected_events==1);
 assert(!pump.reset(1)); assert(pump.reset(2));
}
''')
    binary = tmp_path / "pump"
    subprocess.run(["g++", "-std=c++20", "-O2", "-Wall", "-Wextra", "-Werror", "-pthread", "-I", str(root / "native/audio_core"), str(source), "-o", str(binary)], check=True, timeout=40)
    subprocess.run([str(binary)], check=True, timeout=15)
