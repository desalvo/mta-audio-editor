"""r76 experimental C++ audio-thread-safe queue/planning boundary."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_native_playout_bridge_compiles_and_bypasses_late_blocks(tmp_path):
    compiler = shutil.which('g++') or shutil.which('clang++')
    if compiler is None:
        pytest.skip('C++20 compiler unavailable')
    source = tmp_path / 'bridge.cpp'
    source.write_text(r'''
#include "native/audio_core/vst3_playout_bridge.hpp"
#include <cassert>
#include <cmath>
using namespace mta;
int main() {
  Vst3PlayoutBridge b(8, 2);
  assert(b.valid());
  float dry[] = {0.5f, -0.5f};
  float out[2] = {9, 9};
  std::uint64_t seq=99;
  std::size_t frames=0, channels=0;
  float buffer[1024]{};
  assert(b.callback(dry,out,1,2) && out[0] == 0.0f);
  assert(b.worker_take(seq,buffer,1024,frames,channels));
  assert(seq==0 && frames==1 && channels==2);
  buffer[0]=0.25f; buffer[1]=-0.25f;
  assert(b.worker_return(seq,buffer,frames,channels));
  assert(b.callback(dry,out,1,2) && out[0]==0.0f);
  assert(b.callback(dry,out,1,2) && out[0]==0.25f);
  assert(b.callback(dry,out,1,2) && out[0]==0.5f); // late -> dry
  assert(b.stats().processed==1 && b.stats().bypassed==1);
  // Late seq=1 must never be used for seq=2.
  assert(b.worker_take(seq,buffer,1024,frames,channels) && seq==1);
  buffer[0]=0.75f;
  assert(b.worker_return(seq,buffer,frames,channels));
  assert(b.callback(dry,out,1,2) && out[0]==0.5f);
  assert(b.stats().late >= 1);
  assert(!Vst3PlayoutBridge(2,2).valid());
}
''')
    exe = tmp_path / 'bridge'
    subprocess.run([compiler, '-std=c++20', '-O2', '-Wall', '-Wextra', '-Werror',
                    '-pthread', '-I', str(ROOT), str(source), '-o', str(exe)],
                   check=True, capture_output=True, text=True, timeout=40)
    subprocess.run([str(exe)], check=True, capture_output=True, text=True, timeout=40)


def test_readiness_remains_false_and_callback_performs_no_ipc():
    code = (ROOT / 'native/audio_core/vst3_playout_bridge.hpp').read_text()
    assert 'worker_take' in code and 'worker_return' in code
    assert 'incoming_.push(' in code and 'outgoing_.pop(' in code
    assert 'subprocess' not in code and 'std::mutex' not in code
    assert 'native_host_ready\\":false' in (ROOT / 'native/vst3_probe/main.cpp').read_text()
