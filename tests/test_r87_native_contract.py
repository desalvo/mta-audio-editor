"""r78-r87: compile and exercise immutable native worker/control-plane contracts."""
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_native_contract_cpp_smoke():
    compiler = shutil.which('c++') or shutil.which('g++')
    if not compiler:
        pytest.skip('C++20 compiler not installed')
    code = r'''
#include "vst3_rt_contract.hpp"
#include <array>
#include <cassert>
#include <cmath>
#include <cstdint>
int main() {
  using namespace mta;
  // r78: quantum
  Vst3Quantum q{256,2,48000}; assert(q.valid() && q.accepts(256,2) && !q.accepts(128,2));
  assert((!Vst3Quantum{512,2,32000}.valid()));
  // r79: seek/restart epochs
  EpochClock e; Vst3Token t{e.current(),4}; assert(e.accepts(t)); e.restart(); assert(!e.accepts(t));
  // r80: frame deadline
  FrameDeadline d{100,256}; assert(!d.expired(356) && d.expired(357));
  // r81: compensation
  NativeLatencyBudget fast{128,2,256}, slow{384,3,256};
  assert(fast.total_frames()==640 && fast.alignment_to(slow)==512);
  // r82: cross-fade dry bypass
  BypassRamp ramp(4); ramp.set_bypass(true); float last=0;
  for (int i=0;i<4;i++){ auto x=ramp.mix(0.0f,1.0f); assert(x>=last); last=x; }
  assert(std::fabs(last-1.0f)<0.00001f);
  // r83: sorted automation
  ParameterBlock params; assert(params.add(10,0,0.2f,256));
  assert(params.add(10,255,1.0f,256)); assert(!params.add(10,256,0.3f,256));
  assert(!params.add(10,15,NAN,256)); assert(params.size()==2);params.clear();
  // r84: sorted MIDI
  MidiBlock midi; assert(midi.add(0,0x90,60,100,256));
  assert(!midi.add(256,0x80,60,0,256)); assert(!midi.add(2,0xf8,60,0,256));
  assert(midi.size()==1);midi.clear();
  // r85: circuit-breaker
  WorkerFaultGate gate; assert(!gate.failed());gate.fault();assert(gate.failed());gate.recover();
  assert(!gate.failed());
  // r86: PCM sanitization
  BlockValidation v;float pcm[4]={2.0f,-2.0f,NAN,0.25f};
  assert(!v.sanitize(pcm,2,2));assert(v.clipped==2 && v.nonfinite==1);
  assert(pcm[0]==1 && pcm[1]==-1 && pcm[2]==0);
  // r87: don't enable realtime
  static_assert(!kNativeVst3RealtimeReady);
}
'''
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp)
        source = path / 'smoke.cpp'
        binary = path / 'smoke'
        source.write_text(code)
        subprocess.run([compiler, '-std=c++20', '-Wall', '-Wextra', '-Werror',
                        '-I', str(ROOT / 'native/audio_core'), str(source),
                        '-o', str(binary)], check=True, timeout=30)
        subprocess.run([str(binary)], check=True, timeout=10)


def test_readiness_remains_disabled():
    code = (ROOT / 'native/audio_core/vst3_rt_contract.hpp').read_text()
    assert 'kNativeVst3RealtimeReady = false' in code
    source = (ROOT / 'native/vst3_probe/main.cpp').read_text()
    assert 'native_host_ready' in source
    assert '\\"native_host_ready\\":false' in source
