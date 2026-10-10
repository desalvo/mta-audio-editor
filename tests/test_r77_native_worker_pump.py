"""Native callback/worker separation regression tests."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_worker_pump_and_irregular_callback_shapes(tmp_path):
    compiler = shutil.which('g++') or shutil.which('clang++')
    if not compiler:
        pytest.skip('C++ compiler not installed')
    source = tmp_path / 'test.cpp'
    source.write_text(r'''
#include "native/audio_core/vst3_worker_pump.hpp"
#include <cassert>
#include <limits>
using namespace mta;
int main() {
  Vst3PlayoutBridge bridge(8,1);
  assert(bridge.valid());
  Vst3WorkerPump pump(bridge);
  float in[4]{0.25f, 0.5f, 0.75f, 0.125f};
  float out[4]{};
  assert(bridge.callback(in,out,1,1));
  assert(pump.pump_once([](const float* i, float* o, size_t f, size_t c) {
    for (size_t k=0; k<f*c; ++k) o[k]=i[k]*2;
    return true;
  }));
  assert(bridge.callback(in,out,1,1));
  assert(out[0]==0.5f);
  assert(pump.stats().handled==1);
  // A delayed 1-frame block must not overwrite a 2-frame output slot.
  assert(pump.pump_once([](const float* i, float* o, size_t f, size_t c) {
    for (size_t k=0; k<f*c; ++k) o[k]=i[k];
    return true;
  }));
  out[0]=77.0f; out[1]=77.0f;
  assert(bridge.callback(in,out,2,1));
  assert(out[0]==0.0f && out[1]==0.0f);
  assert(pump.pump_once([](const float*, float* o, size_t, size_t) {
    o[0]=std::numeric_limits<float>::quiet_NaN();
    return true;
  }));
  assert(pump.stats().processing_failures==1);
  assert(bridge.callback(in,out,2,1));
  assert(out[0]==0.25f && out[1]==0.5f);
}
''')
    exe = tmp_path / 'worker'
    subprocess.run([compiler, '-std=c++20', '-O2', '-Wall', '-Wextra', '-Werror',
                    '-pthread', '-I', str(ROOT), str(source), '-o', str(exe)],
                   capture_output=True, text=True, check=True, timeout=30)
    subprocess.run([str(exe)], capture_output=True, text=True, check=True, timeout=30)


def test_not_enabled_yet():
    assert 'native_host_ready\\":false' in (ROOT / 'native/vst3_probe/main.cpp').read_text()
