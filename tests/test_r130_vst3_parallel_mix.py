"""Compiled C++ functional tests for sample-accurate dry/wet latency alignment."""
import shutil
import subprocess
from pathlib import Path
import pytest

def test_native_parallel_mix(tmp_path):
    compiler = shutil.which("g++") or shutil.which("clang++")
    if not compiler:
        pytest.skip("C++ compiler not available")
    base = Path(__file__).resolve().parents[1] / "native" / "audio_core"
    src = tmp_path / "test.cpp"
    src.write_text(r'''
#include "vst3_parallel_mix.hpp"
#include <array>
#include <cassert>
#include <limits>
int main() {
  mta::Vst3ParallelMix m(2, 1);
  assert(m.valid());
  float a[4] {1,2,3,4};
  float w[4] {0,0,10,20};
  float o[4] {};
  assert(m.process(a,w,o,2,1,0.5f));
  assert(o[0]==0 && o[1]==0);
  assert(m.process(a+2,w+2,o+2,2,1,0.5f));
  assert(o[2]==5.5f && o[3]==11.f);
  m.reset();
  assert(m.process(a,nullptr,o,2,1,1.f));
  assert(o[0]==0 && o[1]==0);
  assert(m.process(a+2,nullptr,o+2,2,1,1.f));
  assert(o[2]==1 && o[3]==2);
  m.reset();
  float bad[2] {std::numeric_limits<float>::quiet_NaN(),1};
  assert(!m.process(bad,w,o,2,1,.5f));
  assert(o[0]==0 && o[1]==0);
  // Invalid input must not advance delay state.
  assert(m.process(a,w,o,2,1,0.f));
  assert(o[0]==0 && o[1]==0);
  // Stereo, variable block sizes, dry fallback.
  mta::Vst3ParallelMix stereo(1,2);
  float s[6] {1,10,2,20,3,30};
  float z[6] {};
  assert(stereo.process(s,nullptr,z,1,2,0.9f));
  assert(z[0]==0 && z[1]==0);
  assert(stereo.process(s+2,nullptr,z+2,2,2,0.9f));
  assert(z[2]==1 && z[3]==10 && z[4]==2 && z[5]==20);
  return 0;
}
''')
    binary = tmp_path / "run"
    subprocess.run([compiler,"-std=c++20","-O2","-Wall","-Wextra","-Werror","-pedantic", "-I",str(base),str(src),"-o",str(binary)],check=True,timeout=30)
    subprocess.run([str(binary)],check=True,timeout=10)
