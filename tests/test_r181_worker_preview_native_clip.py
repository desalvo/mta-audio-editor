import os
import shutil
import subprocess
from pathlib import Path

from app.ai_worker_protocol import configured_worker

ROOT = Path(__file__).resolve().parents[1]


def test_generation_endpoints_exist_and_gate_unconfigured_worker(monkeypatch):
    from app.main import app
    monkeypatch.delenv('MTA_AI_WORKER_ENABLED', raising=False)
    assert configured_worker() is None
    paths = {r.path for r in app.routes}
    assert '/api/projects/{pid}/remix/generate' in paths
    assert '/api/projects/{pid}/ai-arranger/generate' in paths


def test_native_soft_clip_compiles_and_handles_nan(tmp_path):
    compiler = shutil.which('g++') or shutil.which('clang++')
    if not compiler:
        import pytest
        pytest.skip('C++ compiler unavailable')
    source = tmp_path / 'test.cpp'
    source.write_text("""#include <cassert>
#include <cmath>
#include "native_soft_clip.hpp"
int main(){float a[]={0.0f, 1.0f, NAN, -2.0f};
  assert(mta::audio::soft_clip(a,2,2));
  assert(a[0] == 0.0f && a[1] > 0.7f && a[1] < 0.8f);
  assert(a[2] == 0.0f && a[3] < -0.9f);
  assert(!mta::audio::soft_clip(a,0,2));
  assert(!mta::audio::soft_clip(a,2,2,100.0f));}
""")
    binary = tmp_path / 'check'
    subprocess.run([compiler, '-std=c++20', '-Wall', '-Wextra', '-Werror',
                    '-I', str(ROOT/'native/audio_core'), str(source), '-o',str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
