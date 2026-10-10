"""C++ native worker regressions: restart isolation, stale PCM, and failures."""
from pathlib import Path
import shutil
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _compile_run(tmp_path, body, *, api=False):
    cc = shutil.which('g++') or shutil.which('clang++')
    if not cc:
        pytest.skip('C++20 compiler missing')
    source = tmp_path / 'stability.cpp'
    source.write_text(body)
    binary = tmp_path / 'stability'
    args = [cc, '-std=c++20', '-O1', '-pthread', '-Wall', '-Wextra', '-Werror',
            '-I', str(ROOT / 'native/audio_core'), str(source)]
    if api:
        args.append(str(ROOT / 'native/audio_core/vst3_runtime_api.cpp'))
    subprocess.run(args + ['-o', str(binary)], check=True, timeout=45)
    subprocess.run([str(binary)], check=True, timeout=25)


def test_worker_clears_previous_pcm_when_processor_only_writes_partially(tmp_path):
    _compile_run(tmp_path, r'''
#include "vst3_worker_pump.hpp"
#include <array>
#include <cassert>
int main() {
 mta::Vst3PlayoutBridge b(16,2); assert(b.valid());
 mta::Vst3WorkerPump pump(b);
 std::array<float,8> in{},out{}; in.fill(0.3f);
 assert(b.callback(in.data(),out.data(),4,2));
 assert(pump.pump_once([](const float*,float* o,std::size_t f,std::size_t c){
   for(std::size_t i=0;i<f*c;++i)o[i]=0.75f;return true;}));
 assert(b.callback(in.data(),out.data(),4,2));
 assert(pump.pump_once([](const float*,float* o,std::size_t,std::size_t){o[0]=0.5f;return true;}));
 assert(b.callback(in.data(),out.data(),4,2));
 for(float v:out) assert(v==0.75f);
 assert(b.callback(in.data(),out.data(),4,2));
 assert(out[0]==0.5f);
 for(std::size_t i=1;i<out.size();++i)assert(out[i]==0.0f);
}
''')


def test_native_api_failure_requires_fresh_runtime(tmp_path):
    _compile_run(tmp_path, r'''
#include "vst3_runtime_api.h"
#include <array>
#include <atomic>
#include <cassert>
#include <chrono>
#include <thread>
static int failing(const float*,float*,uint32_t,uint32_t,void*) {return -1;}
int main(){
 for(int cycle=0;cycle<20;++cycle) {
  void* h=mta_vst3_rt_create(16,2,48000,16,2);assert(h);
  assert(mta_vst3_rt_start(h,failing,nullptr)==0);
  std::array<float,32> in{},out{};in.fill(0.25f);
  for(int i=0;i<100 && mta_vst3_rt_state(h)==1;++i) {
   mta_vst3_rt_process(h,in.data(),out.data(),16,2);
   std::this_thread::sleep_for(std::chrono::microseconds(200));
  }
  assert(mta_vst3_rt_state(h)==2);
  out.fill(1.0f);
  assert(mta_vst3_rt_process(h,in.data(),out.data(),16,2)==-4);
  for(float v:out)assert(v==0.0f);
  mta_vst3_rt_stop(h);
  assert(mta_vst3_rt_start(h,failing,nullptr)!=0);
  MtaVst3RuntimeStatsV1 stats{}; assert(mta_vst3_rt_stopped_stats(h,&stats)==0);
  assert(stats.failures>=1);
  mta_vst3_rt_destroy(h);
 }
}
''', api=True)
