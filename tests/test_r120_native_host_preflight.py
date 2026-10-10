"""r101-r120 readiness checks and fail-closed native runtime lifecycle."""
from pathlib import Path
import shutil
import subprocess
import pytest
ROOT = Path(__file__).resolve().parents[1]

@pytest.mark.parametrize('index', range(20))
def test_each_native_readiness_gate_must_pass(index, tmp_path):
    compiler = shutil.which('g++') or shutil.which('clang++')
    if not compiler:
        pytest.skip('C++20 compiler unavailable')
    code = r'''#include "vst3_runtime_preflight.hpp"
#include <cassert>
int main() {
  using namespace mta;
  WorkerRuntimeConfig c;
  NativeHostEvidence e;
  e.callback_quiescent=true; e.ipc_handshake=true; e.ipc_version=true;
  e.plugin_loaded=true; e.process_verified=true; e.latency_reported=true;
  e.fault_recovery=true; e.midi_verified=true; e.automation_verified=true;
  e.platforms_verified=true; e.realtime_stress_verified=true;
  assert(c.valid());
  auto r=validate_native_host(c,e);
  assert(r.ready_for_review()); assert(r.passed_count()==20);
  assert(!kNativeHostActivationAllowed); assert(!kNativeWorkerRealtimeEnabled);
  // The selected gate is cleared through a direct configuration/evidence mutation.
  switch(INDEX) {
  case 0: c.quantum.frames=0; break;
  case 1: c.quantum.channels=3; break;
  case 2: c.quantum.rate=32000; break;
  case 3: c.queue_blocks=2; c.lookahead_blocks=1; break;
  case 4: c.queue_blocks=4097; break;
  case 5: c.lookahead_blocks=0; break;
  case 6: c.lookahead_blocks=c.queue_blocks; break;
  case 7: c.max_idle_spins=0; break;
  case 8: c.max_idle_spins=4097; break;
  case 9: e.callback_quiescent=false; break;
  case 10: e.ipc_handshake=false; break;
  case 11: e.ipc_version=false; break;
  case 12: e.plugin_loaded=false; break;
  case 13: e.process_verified=false; break;
  case 14: e.latency_reported=false; break;
  case 15: e.fault_recovery=false; break;
  case 16: e.midi_verified=false; break;
  case 17: e.automation_verified=false; break;
  case 18: e.platforms_verified=false; break;
  case 19: e.realtime_stress_verified=false; break;
  }
  r=validate_native_host(c,e);
  assert(!r.ready_for_review());
  assert(!r.passed_check(static_cast<ReadinessCheck>(INDEX)));
  assert(r.passed_count()==19);
} 
'''.replace('INDEX', str(index))
    src = tmp_path/'test.cpp'; src.write_text(code)
    exe=tmp_path/'test'
    cmd=[compiler,'-std=c++20','-Wall','-Wextra','-Werror','-pthread','-I',str(ROOT/'native/audio_core'),str(src),'-o',str(exe)]
    result=subprocess.run(cmd,capture_output=True,text=True)
    assert result.returncode == 0, result.stderr
    result=subprocess.run([str(exe)],capture_output=True,text=True,timeout=10)
    assert result.returncode == 0, result.stderr

def test_worker_restart_requires_fresh_runtime():
    source=(ROOT/'native/audio_core/vst3_worker_runtime.hpp').read_text()
    assert 'if (ever_started_) return false;' in source
    assert 'ever_started_ = true;' in source
    assert 'kNativeWorkerRealtimeEnabled = false' in source
