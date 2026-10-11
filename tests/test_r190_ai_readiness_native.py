"""r190: observable ACE-Step readiness and native gate test."""
from pathlib import Path
import subprocess
from app.ace_step_readiness import readiness

ROOT = Path(__file__).resolve().parents[1]


def test_not_configured_does_not_claim_inference(monkeypatch):
    monkeypatch.delenv('MTA_AI_WORKER_ENABLED', raising=False)
    state = readiness(probe=True)
    assert state['reason'] == 'worker_not_configured'
    assert not state['ready_for_real_generation']
    assert not state['inference_verified']


def test_mock_worker_capabilities_not_inference(monkeypatch, tmp_path):
    worker = tmp_path / 'worker'
    worker.write_text('#!/usr/bin/env python3\nimport json\nprint(json.dumps({"protocol":"mta.ai.worker.v1","supports_audio_input":True}))\n')
    worker.chmod(0o700)
    monkeypatch.setenv('MTA_AI_WORKER_ENABLED', 'true')
    monkeypatch.setenv('MTA_AI_WORKER_EXECUTABLE', str(worker))
    state = readiness(probe=True)
    assert state['worker_capabilities_verified'] and state['accepts_source_audio']
    assert not state['inference_verified'] and not state['ready_for_real_generation']


def test_native_noise_gate(tmp_path):
    source = tmp_path / 'gate.cpp'
    source.write_text('#include "native/audio_core/native_noise_gate.hpp"\n#include <cassert>\nint main(){ float a[]={0.01f,0.3f,-0.8f}; assert(mta::audio::noise_gate(a,3,0.1f)); assert(a[0]==0.f && a[1]==0.3f && a[2]==-0.8f); assert(!mta::audio::noise_gate(a,3,-1.f)); }\n')
    binary = tmp_path / 'gate'
    subprocess.run(['c++','-std=c++20','-I',str(ROOT),str(source),'-o',str(binary)],check=True,capture_output=True)
    subprocess.run([str(binary)],check=True,capture_output=True)
