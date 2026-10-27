import subprocess
from pathlib import Path

import pytest
from app.ai_worker_protocol import configured_worker, run_external_worker, verify_preview_wav, WorkerUnavailable
ROOT = Path(__file__).resolve().parents[1]

def test_worker_requires_admin_opt_in(monkeypatch):
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER', 'true')
    monkeypatch.delenv('MTA_AI_WORKER_ENABLED', raising=False)
    monkeypatch.setenv('MTA_AI_WORKER_EXECUTABLE', '/bin/true')
    assert configured_worker() is None
    with pytest.raises(WorkerUnavailable):
        run_external_worker({'prompt': 'x'})

def test_worker_file_contract_and_validation(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER', 'true')
    script = tmp_path / 'worker.py'
    script.write_text("#!/usr/bin/env python3\nimport argparse, json, wave\np=argparse.ArgumentParser(); p.add_argument('--request'); p.add_argument('--output'); a=p.parse_args()\nassert json.load(open(a.request))['model_id']=='test-model'\nwith wave.open(a.output,'wb') as w:\n w.setnchannels(1);w.setsampwidth(2);w.setframerate(44100);w.writeframes(b'\\0\\0'*441)\n")
    script.chmod(0o700)
    monkeypatch.setenv('MTA_AI_WORKER_ENABLED', 'true')
    monkeypatch.setenv('MTA_AI_WORKER_EXECUTABLE', str(script))
    data, info = run_external_worker({'model_id': 'test-model'}, timeout_seconds=10)
    assert data[:4] == b'RIFF' and info['frames'] == 441

def test_worker_rejects_invalid_audio(tmp_path):
    p = tmp_path / 'bad.wav'; p.write_text('not audio')
    with pytest.raises(ValueError): verify_preview_wav(p)

def test_native_pdc_mix_compiles_and_runs(tmp_path):
    code = r'''#include "native_pdc_mix.hpp"
#include <cassert>
#include <cmath>
int main(){
  mta::Vst3PdcPlan plan{};
  plan.valid=true;plan.count=2;
  plan.routes[0].enabled=true;plan.routes[1].enabled=true;
  plan.routes[0].alignment_frames=0;plan.routes[1].alignment_frames=2;
  mta::NativePdcMix m(plan,1);assert(m.valid());
  assert(m.set_route(0,1.0f,true));assert(m.set_route(1,0.5f,true));
  float a[4]={1,0,0,0},b[4]={1,0,0,0},out[4]={};
  const float* in[]={a,b}; assert(m.process(in,2,out,4));
  assert(std::isfinite(out[0]));assert(!m.set_route(0,NAN,true));
}'''
    src = tmp_path / 'test.cpp'; src.write_text(code)
    binary = tmp_path / 'test'
    subprocess.run(['g++','-std=c++20','-Wall','-Wextra','-pedantic','-I',str(ROOT/'native/audio_core'),str(src),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)
