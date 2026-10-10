"""Public C ABI compiles as C and can be used with the C++ runtime implementation."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_native_header_compiles_with_plain_c(tmp_path):
    cc = shutil.which("cc")
    if not cc:
        pytest.skip("C compiler unavailable")
    src = tmp_path / "consumer.c"
    src.write_text("#include \"vst3_runtime_api.h\"\nint main(void) { MtaVst3ConfigV2 cfg = {0}; MtaVst3PlayoutStatsV2 st = {0}; return (int)(cfg.channels + st.dropped); }\n")
    subprocess.run([cc, "-std=c11", "-Wall", "-Wextra", "-Werror", "-I",
                    str(ROOT / "native/audio_core"), "-c", str(src),
                    "-o", str(tmp_path / "consumer.o")], check=True, timeout=30)


def test_native_api_exact_quantum_and_bounded_silence(tmp_path):
    cc = shutil.which("g++") or shutil.which("clang++")
    if not cc:
        pytest.skip("C++20 compiler unavailable")
    src = tmp_path / "quantum.cpp"
    src.write_text(r'''#include "vst3_runtime_api.h"
#include <array>
#include <cassert>
int main() {
  static_assert(sizeof(MtaVst3ConfigV2) == 20);
  assert(mta_vst3_rt_abi_version() == 2);
  void* h = mta_vst3_rt_create(128, 2, 48000, 16, 4); assert(h);
  MtaVst3ConfigV2 cfg{}; assert(mta_vst3_rt_configuration(h, &cfg) == 0);
  assert(cfg.frames == 128 && cfg.channels == 2);
  std::array<float, 256> in{}, out{};
  in.fill(0.25f); out.fill(0.75f);
  assert(mta_vst3_rt_process(h, in.data(), out.data(), 64, 2) == -2);
  for (std::size_t i = 0; i < 128; ++i) assert(out[i] == 0.0f);
  for (std::size_t i = 128; i < 256; ++i) assert(out[i] == 0.75f);
  out.fill(0.75f);
  assert(mta_vst3_rt_process(h, in.data(), out.data(), 128, 2) == -4);
  for (auto x : out) assert(x == 0.0f);
  mta_vst3_rt_destroy(h);
}''')
    binary = tmp_path / "quantum"
    subprocess.run([cc, "-std=c++20", "-Wall", "-Wextra", "-Werror", "-pthread",
                    "-I", str(ROOT / "native/audio_core"), str(src),
                    str(ROOT / "native/audio_core/vst3_runtime_api.cpp"),
                    "-o", str(binary)], check=True, timeout=45)
    subprocess.run([str(binary)], check=True, timeout=15)
