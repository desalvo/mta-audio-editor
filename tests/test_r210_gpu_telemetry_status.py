"""Process GPU estimates and reasons survive inference without entering billing."""
import json
from pathlib import Path
import subprocess
import time
from types import SimpleNamespace
import pytest
from app import ace_gpu_process_meter as m

@pytest.fixture
def meter(monkeypatch):
    monkeypatch.setattr(m, '_ace_pid', lambda: 55)
    monkeypatch.setattr(m, '_process_identity', lambda pid: 'start-1')
    monkeypatch.setattr(m, '_cpu_seconds', lambda pid: 30)
    monkeypatch.setattr(m, '_drm_counter', lambda pid: None)
    return m.AceProcessMeter('http://127.0.0.1:8001')

def test_drm_process_delta_never_becomes_verified(meter, monkeypatch):
    values = iter([1000000000, 4000000000])
    monkeypatch.setattr(m, '_drm_counter', lambda pid: next(values))
    monkeypatch.setattr(m.subprocess, 'run', lambda *a, **k: pytest.fail('no SMI needed for DRM'))
    assert meter.sample()['gpu_metrics_status'] == 'baseline_only'
    result = meter.sample()
    assert result['gpu_seconds_estimated'] == 3
    assert result['gpu_metrics_source'] == 'drm-fdinfo'
    assert 'gpu_seconds' not in result

@pytest.mark.parametrize('error,reason', [(FileNotFoundError(), 'amd_smi_missing'),
    (subprocess.CalledProcessError(1, 'amd-smi'), 'amd_smi_failed'),
    (subprocess.TimeoutExpired('amd-smi', 4), 'amd_smi_timeout')])
def test_smi_failures_have_safe_reasons(meter, monkeypatch, error, reason):
    def fail(*a, **kw): raise error
    monkeypatch.setattr(m.subprocess, 'run', fail)
    result = meter.sample()
    assert result['gpu_metrics_status'] == reason
    assert 'gpu_seconds_estimated' not in result

def test_zero_is_not_presented_as_verified_idle(meter, monkeypatch):
    monkeypatch.setattr(m.subprocess, 'run', lambda *a, **k: SimpleNamespace(stdout=json.dumps({'PID':55,'USAGE':{'GFX':0}})))
    meter.sample()
    result = meter.sample()
    assert result['gpu_metrics_status'] == 'zero_counter_unverified'
    assert 'gpu_seconds_estimated' not in result

def test_source_switch_reset_and_missing_sample_clear_stale_values(meter, monkeypatch):
    samples = iter([10, 20, 15, None, None])
    monkeypatch.setattr(m, '_drm_counter', lambda pid: next(samples))
    monkeypatch.setattr(m.subprocess, 'run', lambda *a, **k: SimpleNamespace(stdout=json.dumps({'PID':55,'USAGE':{'GFX':1000}})))
    meter.sample()
    assert 'gpu_seconds_estimated' in meter.sample()
    assert meter.sample()['gpu_metrics_status'] == 'counter_reset'
    assert meter.sample()['gpu_metrics_status'] == 'baseline_only'
    monkeypatch.setattr(m.subprocess, 'run', lambda *a, **k: SimpleNamespace(stdout='{}'))
    assert 'gpu_seconds_estimated' not in meter.sample()

def test_reused_pid_is_rejected(meter, monkeypatch):
    monkeypatch.setattr(m, '_process_identity', lambda pid: 'start-2')
    assert meter.sample()['gpu_metrics_status'] == 'process_changed'

def test_gpu_metadata_persists_after_sidecar_removal(tmp_path, monkeypatch):
    from app import ai_arranger_runtime as queue
    monkeypatch.setattr(queue, '_ROOT', tmp_path)
    queue.configure(1)
    def work(progress):
        progress.write_text(json.dumps({'gpu_seconds_estimated': 3.5,
            'gpu_metrics_source':'drm-fdinfo','gpu_metrics_status':'sampled_process'}))
    job = queue.start('project-test', 'ace-step', work)[1]
    for _ in range(100):
        row = queue.get(job['job_id'])
        if row['state'] == 'completed': break
        time.sleep(0.02)
    assert row['state'] == 'completed'
    assert row['gpu_seconds_estimated'] == 3.5
    assert row['gpu_seconds'] is None
    assert row['gpu_metrics_source'] == 'drm-fdinfo'
    assert row['gpu_metrics_status'] == 'sampled_process'
    assert queue._gpu_metadata({'gpu_metrics_source':'token=secret','gpu_metrics_status':'prompt'}) == {}

def test_gpu_reason_visible_in_actual_renderer():
    path = Path(__file__).resolve().parents[1] / 'app/static/app.js'
    text = path.read_text()
    section = text[text.index('let aiArrangerWatchTimer'):text.index('async function aiArrangerWatchActive')]
    script = '''const vm=require('vm'),assert=require('assert');
const elapsed={};const context={tr:(en,it)=>en,document:{getElementById:id=>id==='aiRemixJobElapsed'?elapsed:null},clearInterval(){}};
vm.createContext(context);vm.runInContext(process.argv[1],context);
vm.runInContext("aiArrangerLastSnapshot={state:'running',gpu_metrics_status:'amd_smi_missing'};aiArrangerRenderElapsed()",context);
assert(elapsed.textContent.includes('amd-smi non disponibile'));
vm.runInContext("aiArrangerLastSnapshot.gpu_seconds_estimated=2.5;aiArrangerRenderElapsed()",context);
assert(elapsed.textContent.includes('~2.5 s (ACE process; non fatturabile)'));
'''
    result = subprocess.run(['node','-e',script,section],capture_output=True,text=True,timeout=10)
    assert result.returncode == 0, result.stderr
