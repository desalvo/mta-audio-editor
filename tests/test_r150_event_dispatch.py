"""Native event dispatcher regressions; 10 distinct worker-side scenarios."""
import subprocess
from pathlib import Path


def test_native_event_dispatch(tmp_path):
    root = Path(__file__).resolve().parents[1]
    code = r'''
#include "vst3_event_dispatch.hpp"
#include <cassert>
#include <cmath>
#include <cstdint>
using namespace mta;
class Sink final: public EventSink {
public:
  int notes=0, params=0; int last_offset=-1; bool fail=false;
  bool midi(const NativeMidiEvent& e) noexcept override { ++notes; last_offset=e.offset; return !fail; }
  bool parameter(const NativeParameterEvent& e) noexcept override { ++params; last_offset=e.offset; return !fail; }
};
int main() {
  Sink s; EventDispatcher d(1); Vst3EventPacket p;
  // r141: safe empty block advances exactly once.
  assert(p.initialize(1,0,64) && d.dispatch(p,s) && d.next_sequence()==1);
  // r142: stale packet cannot replay.
  assert(!d.dispatch(p,s) && d.stats().stale==1);
  // r143: future packet does not advance playback.
  assert(p.initialize(1,3,64) && !d.dispatch(p,s) && d.next_sequence()==1);
  // r144: MIDI note on/off and sample offsets survive transport.
  assert(p.initialize(1,1,64)); assert(p.note(2,0x90,60,100)); assert(p.note(30,0x80,60,0));
  assert(d.dispatch(p,s) && s.notes==2 && s.last_offset==30);
  // r145: normalized parameter automation preserves offset.
  assert(p.initialize(1,2,64)); assert(p.parameter(471,7,0.25f));
  assert(d.dispatch(p,s) && s.params==1 && s.last_offset==7);
  // r146: invalid values and out-of-quantum offsets rejected before enqueue.
  assert(p.initialize(1,3,64)); assert(!p.note(64,0x90,60,100));
  assert(!p.parameter(1,64,0.3f)); assert(!p.parameter(1,0,NAN));
  assert(d.dispatch(p,s));
  // r147: sink failures recorded and do not block following sequences.
  assert(p.initialize(1,4,64)); assert(p.note(0,0x90,60,100)); s.fail=true;
  assert(!d.dispatch(p,s) && d.stats().delivery_failures==1);
  s.fail=false; assert(p.initialize(1,5,64) && d.dispatch(p,s));
  // r148: reject wrong epoch; future epoch not consumed.
  assert(p.initialize(2,6,64) && !d.dispatch(p,s) && d.stats().future>=2);
  // r149: seek needs strictly newer epoch, resetting ordering/counters.
  assert(!d.reset(1)); assert(d.reset(2));
  assert(p.initialize(2,0,17) && d.dispatch(p,s));
  // r150: invalid frame count / zero epoch rejected, without delivery.
  assert(p.initialize(2,1,17)); p.frames=0;
  assert(!d.dispatch(p,s) && d.stats().invalid==1);
  assert(!EventDispatcher(0).dispatch(p,s));
  return 0;
}
'''
    cpp = tmp_path / 'events.cpp'
    cpp.write_text(code)
    exe = tmp_path / 'events'
    subprocess.run(['g++', '-std=c++20', '-O2', '-Wall', '-Wextra', '-Werror', '-pthread',
                    '-I', str(root / 'native/audio_core'), str(cpp), '-o', str(exe)], check=True, timeout=40)
    subprocess.run([str(exe)], check=True, timeout=15)
