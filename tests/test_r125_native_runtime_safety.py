"""Native bridge must reject non-finite inputs and reject stopped runtimes."""
from pathlib import Path
import shutil
import subprocess
import pytest
ROOT = Path(__file__).resolve().parents[1]


def test_native_bridge_rejects_invalid_pcm_without_queuing(tmp_path):
    cc = shutil.which("g++") or shutil.which("clang++")
    if not cc:
        pytest.skip("C++20 compiler unavailable")
    src = tmp_path / "pcm.cpp"
    src.write_text(r'''#include "vst3_playout_bridge.hpp"
#include <array>
#include <cassert>
#include <limits>
int main() {
  mta::Vst3PlayoutBridge bridge(16, 2);
  assert(bridge.valid());
  std::array<float, 32> input{}, output{};
  input.fill(0.5f);
  input[5] = std::numeric_limits<float>::quiet_NaN();
  output.fill(0.75f);
  assert(!bridge.callback(input.data(), output.data(), 16, 2));
  for (float v : output) assert(v == 0.0f);
  assert(bridge.stats().submitted == 0);
  input[5] = 0.5f;
  assert(bridge.callback(input.data(), output.data(), 16, 2));
  assert(bridge.stats().submitted == 1);
  input[5] = std::numeric_limits<float>::infinity();
  assert(!bridge.callback(input.data(), output.data(), 16, 2));
  assert(bridge.stats().submitted == 1);
  return 0;
}
''')
    binary = tmp_path / "pcm"
    subprocess.run([cc, "-std=c++20", "-Wall", "-Wextra", "-Werror", "-pthread", "-I", str(ROOT / "native/audio_core"), str(src), "-o", str(binary)], check=True, timeout=45)
    subprocess.run([str(binary)], check=True, timeout=20)


def test_native_api_rejects_unstarted_runtime_and_silences_output(tmp_path):
    cc = shutil.which("g++") or shutil.which("clang++")
    if not cc:
        pytest.skip("C++20 compiler unavailable")
    src = tmp_path / "state.cpp"
    src.write_text(r'''#include <array>
#include <cassert>
#include <cstdint>
extern "C" void* mta_vst3_rt_create(std::uint32_t,std::uint32_t,std::uint32_t,std::uint32_t,std::uint32_t) noexcept;
extern "C" int mta_vst3_rt_process(void*,const float*,float*,std::uint32_t,std::uint32_t) noexcept;
extern "C" void mta_vst3_rt_destroy(void*) noexcept;
int main(){
  auto* h=mta_vst3_rt_create(16,2,48000,16,2); assert(h);
  std::array<float,32> input{},out{}; input.fill(0.5f);out.fill(0.9f);
  assert(mta_vst3_rt_process(h,input.data(),out.data(),16,2)==-4);
  for(auto v:out)assert(v==0.0f);
  mta_vst3_rt_destroy(h);return 0;
}
''')
    binary = tmp_path / "state"
    subprocess.run([cc,"-std=c++20","-Wall","-Wextra","-Werror","-pthread","-I",str(ROOT/"native/audio_core"),str(src),str(ROOT/"native/audio_core/vst3_runtime_api.cpp"),"-o",str(binary)],check=True,timeout=45)
    subprocess.run([str(binary)],check=True,timeout=20)
