import shutil
import subprocess
from pathlib import Path

import pytest


def test_pcm_interleave_roundtrip(tmp_path):
    compiler = shutil.which('g++') or shutil.which('clang++')
    if compiler is None:
        pytest.skip('C++ compiler unavailable')
    root = Path(__file__).resolve().parents[1]
    source = tmp_path / 'pcm.cpp'
    source.write_text(r'''#include "native_pcm_interleave.hpp"
#include <cassert>
#include <cmath>
int main() {
 float left[]={1.f,2.f},right[]={3.f,4.f};
 const float* planes[]={left,right};float interleaved[4]={};
 assert(mta::audio::interleave_pcm(planes,interleaved,2,2));
 assert(interleaved[0]==1.f && interleaved[1]==3.f && interleaved[2]==2.f && interleaved[3]==4.f);
 float lout[2]={},rout[2]={};float* outputs[]={lout,rout};
 assert(mta::audio::deinterleave_pcm(interleaved,outputs,2,2));
 assert(lout[1]==2.f && rout[1]==4.f);
 float sentinel[]={55.f,55.f,55.f,55.f};left[0]=NAN;
 assert(!mta::audio::interleave_pcm(planes,sentinel,2,2));
 assert(sentinel[0]==55.f && sentinel[3]==55.f);
 assert(!mta::audio::interleave_pcm(planes,sentinel,0,2));
}
''')
    binary = tmp_path / 'pcm'
    subprocess.run([compiler, '-std=c++20', '-Wall', '-Wextra', '-Werror', '-I', str(root/'native/audio_core'), str(source), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)


def test_worker_manifest_cannot_be_supplied_as_output_path():
    from app.ai_worker_protocol import _SAFE_AUDIO_NAME, MAX_SOURCE_DURATION_SECONDS
    assert not _SAFE_AUDIO_NAME.fullmatch('../other.wav')
    assert MAX_SOURCE_DURATION_SECONDS == 1800
