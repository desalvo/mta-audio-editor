from pathlib import Path
import subprocess
import tempfile

from app.ai_job_queue import AIJobQueue

ROOT = Path(__file__).resolve().parents[1]


def test_ai_plan_cannot_be_mutated_after_submit_or_get():
    jobs = AIJobQueue()
    plan = {'constraints': {'chords': ['Am', 'F']}}
    created = jobs.submit('project-1', 'owner-1', 'remix', plan)
    plan['constraints']['chords'].append('G')
    created['plan']['constraints']['chords'].append('C')
    result = jobs.get(created['id'], 'project-1', 'owner-1')
    assert result['plan']['constraints']['chords'] == ['Am', 'F']
    result['plan']['constraints']['chords'].append('Dm')
    assert jobs.get(created['id'], 'project-1', 'owner-1')['plan']['constraints']['chords'] == ['Am', 'F']
    assert jobs.get(created['id'], 'project-1', 'owner-2') is None
    assert jobs.cancel(created['id'], 'project-1', 'owner-2') is None
    assert jobs.cancel(created['id'], 'project-1', 'owner-1')['status'] == 'cancelled'


def test_mix_matrix_compiled_with_mute_gain_nan_safety():
    code = r'''#include "native_mix_matrix.hpp"
#include <cassert>
#include <cmath>
#include <limits>
int main(){
  float a[]={1.0f,-1.0f}, b[]={0.5f,0.5f}, out[]={99.0f,99.0f};
  mta::NativeMixRoute routes[]={{a,0.5f,true},{b,1.0f,true}};
  assert(mta::mix_native_pcm(routes,2,out,2,1));
  assert(std::fabs(out[0]-1.0f)<1e-6f && std::fabs(out[1])<1e-6f);
  routes[1].enabled=false;
  assert(mta::mix_native_pcm(routes,2,out,2,1));
  assert(std::fabs(out[0]-0.5f)<1e-6f && std::fabs(out[1]+0.5f)<1e-6f);
  routes[0].gain=std::numeric_limits<float>::quiet_NaN();
  out[0]=42.0f;
  assert(!mta::mix_native_pcm(routes,2,out,2,1));
  assert(out[0]==42.0f);
  routes[0].gain=1.0f;
  a[0]=std::numeric_limits<float>::infinity();
  assert(!mta::mix_native_pcm(routes,2,out,2,1));
}
'''
    with tempfile.TemporaryDirectory() as temp:
        source = Path(temp) / 'test.cpp'
        target = Path(temp) / 'mix_test'
        source.write_text(code)
        subprocess.run(['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror', '-I', str(ROOT / 'native/audio_core'), str(source), '-o', str(target)], check=True, timeout=30)
        subprocess.run([str(target)], check=True, timeout=15)
