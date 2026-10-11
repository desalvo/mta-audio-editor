from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def test_native_pdc_processor_compiled_real_alignment():
    code = r'''#include "vst3_pdc_processor.hpp"
#include <cassert>
#include <cmath>
#include <limits>
int main() {
  mta::Vst3PdcRoute routes[2]{};
  routes[0].plugin_frames=3;
  routes[1].plugin_frames=1;
  auto plan=mta::make_vst3_pdc_plan(routes,2);
  assert(plan.valid && plan.target_frames==3 && plan.routes[1].alignment_frames==2);
  mta::Vst3PdcProcessor processor(plan,1);
  assert(processor.valid());
  float a[4]={1,0,0,0}, b[4]={1,0,0,0}, out[4]={};
  const float* inputs[2]={a,b};
  assert(processor.process(inputs,2,out,4));
  assert(std::fabs(out[0]-0.5f)<1e-5f);
  assert(std::fabs(out[1])<1e-5f);
  assert(std::fabs(out[2]-0.5f)<1e-5f);
  processor.reset();
  assert(!processor.process(inputs,1,out,4));
  b[0]=std::numeric_limits<float>::quiet_NaN();
  assert(!processor.process(inputs,2,out,4));
  mta::Vst3PdcPlan invalid{};
  assert(!mta::Vst3PdcProcessor(invalid,1).valid());
}
'''
    with tempfile.TemporaryDirectory() as td:
        source = Path(td) / 'test.cpp'
        binary = Path(td) / 'pdc_test'
        source.write_text(code)
        subprocess.run(['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror', '-I', str(ROOT / 'native/audio_core'), str(source), '-o', str(binary)], check=True, timeout=30)
        subprocess.run([str(binary)], check=True, timeout=15)
