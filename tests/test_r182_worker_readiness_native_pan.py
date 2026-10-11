import shutil
import subprocess
from pathlib import Path

from app.ai_worker_protocol import worker_capabilities

ROOT = Path(__file__).resolve().parents[1]

def test_worker_status_fail_closed(monkeypatch):
    monkeypatch.delenv('MTA_AI_WORKER_ENABLED', raising=False)
    assert worker_capabilities()['worker_configured'] is False
    assert worker_capabilities()['inference_verified'] is False
    assert worker_capabilities()['ace_step_ready'] is False
    from app.main import app
    assert '/api/ai-arranger/worker-status' in set(app.openapi()["paths"])

def test_native_pan_compiles_and_ramps(tmp_path):
    compiler = shutil.which('g++') or shutil.which('clang++')
    if not compiler:
        import pytest
        pytest.skip('C++20 compiler unavailable')
    source = tmp_path/'pan.cpp'
    source.write_text('#include <cassert>\n#include <cmath>\n#include "native_stereo_pan.hpp"\nint main(){\n  mta::audio::StereoPanRamp pan; float pcm[]={1.f,1.f,1.f,1.f};\n  assert(pan.process(pcm,2,1.f));\n  assert(pcm[0] > 0.f && pcm[0] < 1.f && pcm[1]==1.f);\n  assert(pcm[2]==0.f && pcm[3]==1.f);\n  assert(!pan.process(pcm,2,2.f));\n  assert(pan.current==1.f);\n}\n')
    binary=tmp_path/'pan'
    subprocess.run([compiler,'-std=c++20','-Wall','-Wextra','-Werror',
                    '-I',str(ROOT/'native/audio_core'),str(source),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)
