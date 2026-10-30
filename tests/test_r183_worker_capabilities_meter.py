import shutil
import subprocess
from pathlib import Path
from app.ai_worker_protocol import worker_capabilities, probe_worker

ROOT=Path(__file__).resolve().parents[1]

def test_worker_probe_fail_closed_without_configuration(monkeypatch):
    monkeypatch.delenv('MTA_AI_WORKER_ENABLED',raising=False)
    assert probe_worker()['probe_ok'] is False
    assert worker_capabilities()['ace_step_ready'] is False


def test_worker_probe_does_not_claim_inference(monkeypatch,tmp_path,synthetic_worker_resolution):
    script=tmp_path/'worker'
    script.write_text('#!/usr/bin/env python3\nimport json,sys\nprint(json.dumps({"protocol":"mta.ai.worker.v1","models":["ace-step-1.5"],"supports_audio_input":True}))\n')
    script.chmod(0o700)
    monkeypatch.setenv('MTA_AI_WORKER_ENABLED','true')
    monkeypatch.setenv('MTA_AI_WORKER_EXECUTABLE',str(script))
    result=probe_worker()
    assert result['probe_ok'] is True
    assert result['declared_models']==['ace-step-1.5']
    assert worker_capabilities()['inference_verified'] is False


def test_native_peak_meter_compiles_and_measures(tmp_path):
    compiler=shutil.which('g++') or shutil.which('clang++')
    if not compiler:
        import pytest
        pytest.skip('C++20 compiler not installed')
    src=tmp_path/'test.cpp'
    src.write_text('''#include "native_peak_meter.hpp"
#include <cassert>
#include <cmath>
int main(){mta::audio::NativePeakMeter m; float p[]={1.f,0.f,-1.f,0.5f};
assert(m.process(p,2,2));assert(m.peak(0)==1.f);assert(m.peak(1)==0.5f);
assert(std::fabs(m.rms(0)-1.f)<0.0001f);
float bad[]={NAN};assert(!m.process(bad,1,1));assert(m.peak(0)==1.f);
m.reset();assert(m.peak(0)==0.f);}
''')
    bin=tmp_path/'test'
    subprocess.run([compiler,'-std=c++20','-Wall','-Wextra','-Werror','-I',str(ROOT/'native/audio_core'),str(src),'-o',str(bin)],check=True)
    subprocess.run([str(bin)],check=True)
