"""Cumulative r88-r100: native control-plane worker lifecycle and playout."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_readiness_remains_disabled():
    source = (ROOT / "native/audio_core/vst3_worker_runtime.hpp").read_text()
    assert "kNativeWorkerRealtimeEnabled = false" in source
    assert "std::thread" in source
    assert "Vst3WorkerPump pump(bridge_)" in source
    assert "std::this_thread::sleep_for" in source
    assert "WorkerRuntimeState::faulted" in source
    main = (ROOT / "native/vst3_probe/main.cpp").read_text()
    assert r'native_host_ready\":false' in main


def test_native_runtime_compiled_and_exercised(tmp_path):
    compiler = shutil.which("g++") or shutil.which("clang++")
    if not compiler:
        pytest.skip("C++20 compiler unavailable")
    test = tmp_path / "main.cpp"
    test.write_text(r'''#include "vst3_worker_runtime.hpp"
#include <array>
#include <cassert>
#include <chrono>
#include <cmath>
#include <thread>
int main() {
  using namespace mta;
  WorkerRuntimeConfig invalid; invalid.queue_blocks = 2; assert(!invalid.valid());
  WorkerRuntimeConfig c; c.quantum = {8,1,48000};
  Vst3WorkerRuntime runtime(c);
  assert(runtime.valid());
  assert(!kNativeWorkerRealtimeEnabled);
  assert(runtime.start([](const float* in,float* out,std::size_t frames,std::size_t chans){
    for(std::size_t i=0;i<frames*chans;++i) out[i]=in[i]*0.5f;
    return true;
  }));
  assert(!runtime.start([](const float*,float*,std::size_t,std::size_t){return true;}));
  std::array<float,8> input{}; input.fill(0.8f);
  std::array<float,8> output{};
  for(int i=0;i<250;++i) {
    assert(runtime.bridge().callback(input.data(),output.data(),8,1));
    std::this_thread::sleep_for(std::chrono::microseconds(150));
  }
  runtime.stop();
  assert(runtime.state()==WorkerRuntimeState::stopped);
  assert(runtime.stopped_stats().completions>0);
  assert(!runtime.healthy());
  Vst3WorkerRuntime faulty(c);
  assert(faulty.start([](const float*,float*,std::size_t,std::size_t){return false;}));
  bool saw_fault=false;
  for(int i=0;i<100 && !saw_fault;++i){
    assert(faulty.bridge().callback(input.data(),output.data(),8,1));
    std::this_thread::sleep_for(std::chrono::milliseconds(1));
    saw_fault=faulty.state()==WorkerRuntimeState::faulted;
  }
  assert(saw_fault);
  faulty.stop();
  return 0;
}
''')
    exe = tmp_path / "runtime"
    build = subprocess.run([compiler, "-std=c++20", "-Wall", "-Wextra", "-Werror", "-pthread", "-I", str(ROOT / "native/audio_core"), str(test), "-o", str(exe)], capture_output=True, text=True)
    assert build.returncode == 0, build.stderr
    run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=15)
    assert run.returncode == 0, run.stderr
