"""Compile and exercise bounded native PCM block transport independently of Python IPC."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_native_block_queue_contract(tmp_path):
    compiler = shutil.which('g++') or shutil.which('clang++')
    if not compiler:
        pytest.skip('C++20 compiler not installed')
    cpp = tmp_path / 'test.cpp'
    cpp.write_text(r"""
#include "native/audio_core/block_spsc.hpp"
#include <cassert>
#include <cmath>
#include <cstdint>
#include <limits>
#include <thread>
using namespace mta;
int main() {
  BlockSpsc q(2);
  assert(q.valid());
  float a[4] = {0.25f, 0.5f, 0.75f, 1.0f};
  assert(q.push(19, a, 2, 2));
  assert(q.push(20, a, 4, 1));
  assert(!q.push(21, a, 2, 2)); // full; never overwrite
  assert(q.pending() == 2);
  std::uint64_t seq=0; std::size_t frames=0, channels=0;
  float out[1024] = {};
  assert(!q.pop(seq, out, 3, frames, channels)); // don't consume partial
  assert(q.pending() == 2);
  assert(q.pop(seq, out, 1024, frames, channels));
  assert(seq == 19 && frames == 2 && channels == 2 && out[3] == 1.0f);
  assert(q.push(21, a, 2, 2)); // wrapped position
  assert(q.pop(seq, out, 1024, frames, channels) && seq == 20);
  assert(q.pop(seq, out, 1024, frames, channels) && seq == 21);
  assert(!q.pop(seq, out, 1024, frames, channels));
  float bad[] = {std::numeric_limits<float>::quiet_NaN()};
  assert(!q.push(3, bad, 1, 1));
  assert(!q.push(3, a, 513, 1));
  assert(!q.push(3, a, 1, 3));
  assert(!BlockSpsc(0).valid());
  BlockSpsc concurrent(8);
  constexpr int iterations=20000;
  std::thread producer([&] {
    for (int i=0;i<iterations;++i) {
      float sample = static_cast<float>(i);
      while (!concurrent.push(i, &sample, 1, 1)) std::this_thread::yield();
    }
  });
  for (int i=0;i<iterations;++i) {
    while (!concurrent.pop(seq, out, 1024, frames, channels)) std::this_thread::yield();
    assert(seq == static_cast<std::uint64_t>(i));
    assert(frames == 1 && channels == 1 && out[0] == float(i));
  }
  producer.join();
  assert(concurrent.pending() == 0);
}
""")
    exe = tmp_path / 'queue-test'
    subprocess.run([compiler, '-std=c++20', '-O2', '-Wall', '-Wextra', '-Werror',
                    '-pthread', '-I', str(ROOT), str(cpp), '-o', str(exe)],
                   check=True, timeout=45, capture_output=True, text=True)
    subprocess.run([str(exe)], check=True, timeout=45, capture_output=True, text=True)


def test_native_host_remains_disabled():
    source = (ROOT / 'native/vst3_probe/main.cpp').read_text()
    assert 'native_host_ready' in source
    assert 'false' in source
    assert (ROOT / 'native/audio_core/block_spsc.hpp').exists()
