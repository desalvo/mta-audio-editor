"""Five native host functional increments: failure isolation and MIDI queue."""
import shutil
import subprocess
from pathlib import Path
import pytest


def test_native_worker_event_pipeline(tmp_path):
    compiler = shutil.which("g++") or shutil.which("clang++")
    if not compiler:
        pytest.skip("C++20 compiler not installed")
    root = Path(__file__).resolve().parents[1]
    source = tmp_path / "integration.cpp"
    source.write_text(r'''#include "vst3_worker_pump.hpp"
#include "vst3_worker_events.hpp"
#include <cassert>
#include <cmath>
#include <stdexcept>
#include <thread>
#include <atomic>
int main() {
  // r136: C++ exceptions in processor are handled by worker; dry fallback remains possible.
  mta::Vst3PlayoutBridge bridge(16, 2, 8, 1);
  assert(bridge.valid());
  mta::Vst3WorkerPump pump(bridge);
  float input[8]{1,0,0,0,0,0,0,0}, output[8]{};
  assert(bridge.callback(input, output, 8, 1));
  assert(pump.pump_once([](const float*,float*,size_t,size_t)->bool {
    throw std::runtime_error("plugin worker exception");
  }));
  assert(pump.stats().processor_exceptions == 1);
  assert(pump.stats().processing_failures == 1);
  // r137: nonfinite worker PCM output is rejected; no poisonous result is enqueued.
  assert(bridge.callback(input, output, 8, 1));
  assert(pump.pump_once([](const float*,float* dst,size_t,size_t)->bool {
    dst[0] = std::nanf(""); return true;
  }));
  assert(pump.stats().processing_failures == 2);
  assert(bridge.callback(input, output, 8, 1));
  assert(output[0] == 1); // deterministic delayed dry fallback.
  // r138: events are carried through a preallocated SPSC queue.
  mta::Vst3WorkerEvents events(4);
  assert(events.valid());
  mta::Vst3EventPacket event{};
  assert(event.initialize(1, 0, 8));
  assert(event.note(1,0x90,60,127));
  assert(event.parameter(7,3,0.5f));
  assert(events.push(event));
  mta::Vst3EventPacket received{};
  assert(events.take_for(1,0,8,received));
  assert(received.matches(1,0,8));
  assert(!events.take_for(1,0,8,received));
  // r139: bounded stale-drop across seek, future events kept for correct block.
  for (int seq=0;seq<3;++seq) {
    assert(event.initialize(4,seq,8)); assert(events.push(event));
  }
  assert(!events.take_for(5,0,8,received,2));
  assert(events.pending()==1);
  assert(!events.take_for(5,0,8,received));
  assert(events.pending()==0);
  assert(event.initialize(6,9,8)); assert(events.push(event));
  assert(!events.take_for(6,8,8,received)); assert(events.pending()==1);
  assert(events.take_for(6,9,8,received));
  // r140: deterministic producer/consumer transfer under concurrency.
  mta::Vst3WorkerEvents concurrent(32);
  std::atomic<int> completed{0};
  std::thread producer([&]{
    mta::Vst3EventPacket item{};
    for(int i=0;i<20000;++i){
      assert(item.initialize(100,static_cast<std::uint64_t>(i),8));
      while(!concurrent.push(item)) std::this_thread::yield();
    }
  });
  std::thread consumer([&]{
    mta::Vst3EventPacket item{};
    for(int i=0;i<20000;++i){
      while(!concurrent.take_for(100,static_cast<std::uint64_t>(i),8,item))
        std::this_thread::yield();
      assert(item.sequence==static_cast<std::uint64_t>(i));
      ++completed;
    }
  });
  producer.join();consumer.join();
  assert(completed==20000 && concurrent.pending()==0);
}
''')
    binary = tmp_path / "integration"
    subprocess.run([compiler, "-std=c++20", "-pthread", "-O2", "-Wall", "-Wextra", "-Werror", "-pedantic", "-I", str(root / "native/audio_core"), str(source), "-o", str(binary)], check=True, timeout=30)
    subprocess.run([str(binary)], check=True, timeout=30)
