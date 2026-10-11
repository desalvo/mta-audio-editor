from pathlib import Path
import shutil
import subprocess
import tempfile

from app.ai_arranger import assess_plan

ROOT = Path(__file__).resolve().parents[1]

def test_preflight_is_truthful_and_actionable():
    plan = {'constraints': {'preserve_chords': True, 'preserve_structure': True},
            'musical_context': {'chords': [], 'sections': []}, 'scope': 'project'}
    result = assess_plan(plan)
    assert not result['generation_ready']
    assert not result['preservation_verified']
    assert {x['code'] for x in result['issues']} == {
        'NO_CHORD_ANNOTATIONS', 'NO_SECTION_MARKERS', 'MODEL_WORKER_NOT_CONFIGURED'}

def test_preflight_range_diagnostic():
    result = assess_plan({'constraints': {}, 'musical_context': {},
                          'scope': 'range', 'start_ms': 250, 'end_ms': 500})
    assert 'SHORT_SELECTION' in {x['code'] for x in result['issues']}

def test_gain_ramp_cpp20():
    compiler = shutil.which('g++') or shutil.which('clang++')
    if not compiler:
        import pytest
        pytest.skip('C++ compiler unavailable')
    code = r"""
#include "native_gain_ramp.hpp"
#include <cassert>
#include <cmath>
int main() {
  mta::NativeGainRamp r;
  float in[8] = {1,1,1,1,1,1,1,1}, out[8] = {};
  assert(r.reset(0.0f));
  assert(r.process(in,out,4,2,1.0f));
  assert(std::fabs(out[0]-0.25f)<1e-6f);
  assert(std::fabs(out[6]-1.0f)<1e-6f);
  assert(!r.process(in,out,4,2,NAN));
  assert(std::fabs(r.current()-1.0f)<1e-6f);
  assert(r.process(in,out,4,2,0.0f));
  assert(std::fabs(out[6])<1e-6f);
}
"""
    with tempfile.TemporaryDirectory() as d:
        source = Path(d) / 'test.cpp'
        exe = Path(d) / 'test'
        source.write_text(code)
        subprocess.run([compiler,'-std=c++20','-Wall','-Wextra','-Werror',
                        '-I',str(ROOT/'native/audio_core'),str(source),'-o',str(exe)], check=True)
        subprocess.run([str(exe)],check=True)
