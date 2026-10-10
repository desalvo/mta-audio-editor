"""ABI v2 configuration and callback-affine telemetry are exercised from C++."""
from pathlib import Path
import shutil
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]

def test_native_vst3_abi_v2_configuration_and_counters(tmp_path):
    compiler = shutil.which("g++") or shutil.which("clang++")
    if not compiler:
        pytest.skip("C++20 compiler unavailable")
    source = tmp_path / "abi.cpp"
    source.write_text(r'''
#include <array>
#include <cassert>
#include <cstdint>
struct Cfg { std::uint32_t frames, channels, rate, capacity, lookahead; };
struct Stats { std::uint64_t submitted, dropped, processed, bypassed, late, exhausted; };
extern "C" std::uint32_t mta_vst3_rt_abi_version() noexcept;
extern "C" void* mta_vst3_rt_create(std::uint32_t,std::uint32_t,std::uint32_t,std::uint32_t,std::uint32_t) noexcept;
extern "C" int mta_vst3_rt_configuration(const void*, Cfg*) noexcept;
extern "C" int mta_vst3_rt_callback_stats(const void*, Stats*) noexcept;
extern "C" void mta_vst3_rt_destroy(void*) noexcept;
int main() {
 assert(mta_vst3_rt_abi_version()==2);
 Cfg c{}; Stats s{};
 assert(mta_vst3_rt_configuration(nullptr,&c)==-1);
 assert(mta_vst3_rt_callback_stats(nullptr,&s)==-1);
 void* h=mta_vst3_rt_create(128,2,48000,16,4); assert(h);
 assert(mta_vst3_rt_configuration(h,&c)==0);
 assert(c.frames==128 && c.channels==2 && c.rate==48000 && c.capacity==16 && c.lookahead==4);
 assert(mta_vst3_rt_callback_stats(h,&s)==0);
 assert(s.submitted==0 && s.processed==0 && s.exhausted==0);
 mta_vst3_rt_destroy(h);
}
''')
    executable = tmp_path / "abi"
    subprocess.run([compiler,"-std=c++20","-Wall","-Wextra","-Werror","-pthread",
                    "-I",str(ROOT / "native/audio_core"),str(source),
                    str(ROOT / "native/audio_core/vst3_runtime_api.cpp"),"-o",str(executable)],
                   check=True, timeout=45)
    subprocess.run([str(executable)], check=True, timeout=20)
