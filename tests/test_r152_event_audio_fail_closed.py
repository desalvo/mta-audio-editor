"""C++ acceptance: MIDI/automation events must not be silently discarded."""
import subprocess
from pathlib import Path


def test_event_pcm_shape_and_backlog_fail_closed(tmp_path):
    root = Path(__file__).resolve().parents[1]
    source = tmp_path / "event_fail_closed.cpp"
    source.write_text(r'''
#include "vst3_event_audio_pump.hpp"
#include <cassert>
using namespace mta;
struct Sink : EventSink {
 int count=0;
 bool midi(const NativeMidiEvent&) noexcept override {++count;return true;}
 bool parameter(const NativeParameterEvent&) noexcept override {++count;return true;}
};
int main() {
 float input[8]={1,1,1,1,1,1,1,1}; float output[8]{};
 auto work=[](const float* in,float* out,std::size_t f,std::size_t c) {
   for (std::size_t i=0;i<f*c;++i) out[i]=in[i]*2;
   return true;
 };
 // A matching event sequence with wrong frame length rejects the audio.
 {
 Vst3PlayoutBridge pcm(16,2,8,1); Vst3WorkerEvents events(16);
 Vst3EventAudioPump pump(pcm,events,1); Sink sink;
 Vst3EventPacket bad; assert(bad.initialize(1,0,4));
 assert(bad.note(0,0x90,60,100)); assert(events.push(bad));
 assert(pcm.callback(input,output,8,1));
 assert(pump.pump_once(sink,work));
 assert(pump.stats().rejected_events==1 && pump.stats().processed==0);
 assert(sink.count==0);
 }
 // Eight stale packets may conceal the matching one. Never execute the
 // audio on the first attempt with an accidentally empty event set.
 {
 Vst3PlayoutBridge pcm(32,2,8,1); Vst3WorkerEvents events(32);
 Vst3EventAudioPump pump(pcm,events,2); Sink sink;
 Vst3EventPacket p;
 for(std::uint64_t i=0;i<8;++i) {
   assert(p.initialize(1,i,8));assert(p.note(0,0x90,60,100));assert(events.push(p));
 }
 assert(p.initialize(2,0,8)); assert(p.note(1,0x90,66,80)); assert(events.push(p));
 assert(pcm.callback(input,output,8,1));
 assert(pump.pump_once(sink,work));
 assert(pump.stats().rejected_events==1 && sink.count==0);
 // Packet 2/0 is still queued; it must never leak into the wrong block.
 assert(events.pending()==1);
 }
 // A future event does not prevent a legitimately eventless block.
 {
 Vst3WorkerEvents events(16);Vst3EventPacket p,out;
 assert(p.initialize(1,4,8)); assert(events.push(p));
 assert(events.take_for_checked(1,3,8,out)==EventTakeResult::empty);
 assert(events.pending()==1);
 assert(events.take_for_checked(1,4,8,out)==EventTakeResult::matched);
 }
}
''')
    binary = tmp_path / "event_fail_closed"
    subprocess.run(["g++", "-std=c++20", "-O2", "-Wall", "-Wextra", "-Werror",
                    "-pthread", "-I", str(root / "native/audio_core"),
                    str(source), "-o", str(binary)], check=True, timeout=35)
    subprocess.run([str(binary)], check=True, timeout=15)
