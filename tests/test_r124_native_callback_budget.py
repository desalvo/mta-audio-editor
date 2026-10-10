"""Realtime callback has a strict upper bound even with stale result backlog."""
from pathlib import Path
import shutil
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_bounded_native_callback_result_polls(tmp_path):
    compiler = shutil.which("g++") or shutil.which("clang++")
    if not compiler:
        pytest.skip("C++20 compiler not available")
    src = tmp_path / "main.cpp"
    src.write_text(r'''#include "vst3_playout_bridge.hpp"
#include <array>
#include <cassert>
int main() {
  mta::Vst3PlayoutBridge bridge(64, 1);
  assert(bridge.valid());
  std::array<float, 16> input{}, output{}, work{};
  input.fill(0.5f);
  // Build a backlog of successful results, all stale by callback #21.
  for (int i = 0; i < 20; ++i) {
    assert(bridge.callback(input.data(), output.data(), 16, 1));
  }
  for (int i = 0; i < 20; ++i) {
    std::uint64_t seq = 0;
    std::size_t frames = 0, channels = 0;
    assert(bridge.worker_take(seq, work.data(), work.size(), frames, channels));
    assert(bridge.worker_return(seq, work.data(), frames, channels));
  }
  assert(bridge.callback(input.data(), output.data(), 16, 1));
  auto stat = bridge.stats();
  assert(stat.late == 8);
  assert(stat.poll_budget_exhausted == 1);
  assert(stat.bypassed > 0);
  assert(output[0] == 0.5f);  // dry fallback for expected sequence 19
  return 0;
}
''')
    binary = tmp_path / "budget"
    subprocess.run([compiler, "-std=c++20", "-Wall", "-Wextra", "-Werror", "-pthread",
                    "-I", str(ROOT / "native/audio_core"), str(src), "-o", str(binary)],
                   check=True, timeout=45)
    subprocess.run([str(binary)], check=True, timeout=20)
