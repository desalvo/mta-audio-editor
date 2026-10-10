"""Compile and run native dry-path latency compensation tests."""
import shutil
import subprocess
from pathlib import Path

import pytest


def test_native_latency_delayline(tmp_path):
    compiler = shutil.which("g++") or shutil.which("clang++")
    if not compiler:
        pytest.skip("C++ compiler unavailable")
    header_dir = Path(__file__).resolve().parents[1] / "native" / "audio_core"
    source = tmp_path / "test.cpp"
    source.write_text(r"""
#include "vst3_latency_line.hpp"
#include <array>
#include <cassert>
#include <limits>
int main() {
  mta::Vst3LatencyLine d(3,2);
  assert(d.valid() && d.delay_frames()==3);
  std::array<float,12> in{1,10, 2,20, 3,30, 4,40, 5,50, 6,60};
  std::array<float,12> out{};
  assert(d.process(in.data(),out.data(),2,2));
  assert(d.process(in.data()+4,out.data()+4,1,2));
  assert(d.process(in.data()+6,out.data()+6,3,2));
  for(int i=0;i<6;++i) {
    assert(out[2*i] == (i<3 ? 0 : float(i-2)));
    assert(out[2*i+1] == (i<3 ? 0 : float((i-2)*10)));
  }
  d.reset();
  std::array<float,2> start{9,90}, first{-1,-1};
  assert(d.process(start.data(),first.data(),1,2));
  assert(first[0]==0 && first[1]==0);
  mta::Vst3LatencyLine zero(0,1);
  float x[3]{1,2,3};
  assert(zero.process(x,x,3,1) && x[0]==1 && x[1]==2 && x[2]==3);
  mta::Vst3LatencyLine mono(2,1);
  float ip[4]{1,2,3,4};
  assert(mono.process(ip,ip,4,1) && ip[0]==0 && ip[1]==0 && ip[2]==1 && ip[3]==2);
  float bad[1]{std::numeric_limits<float>::quiet_NaN()};
  float y[1]{42};
  assert(!mono.process(bad,y,1,1) && y[0]==0);
  assert(!mono.process(ip,y,1,2));
}
""")
    binary = tmp_path / "test"
    subprocess.run([compiler, "-std=c++20", "-O2", "-Wall", "-Wextra", "-Werror", "-pedantic", "-I", str(header_dir), str(source), "-o", str(binary)], check=True, timeout=30)
    subprocess.run([str(binary)], check=True, timeout=10)
