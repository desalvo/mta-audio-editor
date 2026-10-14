import json
import pytest
from app.ai_amd_smi_collector import GPUAttributionError
from app import ai_gpu_attribution_report as reporting


def test_no_unverified_host_access(monkeypatch):
    monkeypatch.setattr(reporting, 'collect_process_snapshot', lambda **kw: pytest.fail('unexpected SMI call'))
    with pytest.raises(GPUAttributionError):
        reporting.collect_attribution_report(job_cgroups={'job':'/jobs/j'})


def test_end_to_end_verified_host_process(tmp_path, monkeypatch):
    (tmp_path / '55').mkdir()
    (tmp_path / '55' / 'cgroup').write_text('0::/jobs/j/worker\n')
    monkeypatch.setattr(reporting, 'collect_process_snapshot', lambda **kw: {
        'gpu_index':0, 'source':'amd-smi-process-json',
        'processes':{55:{'gfx_ns':10, 'memory_bytes':1024, 'gpu_index':0}}})
    result = reporting.collect_attribution_report(job_cgroups={'job':'/jobs/j'}, proc_root=tmp_path,
                                                   host_pid_namespace_verified=True)
    assert result['attribution_verified'] is True
    assert result['processes'][0]['job_id'] == 'job'
    assert result['measured_gpu_seconds'] is None
    assert result['billing_eligible'] is False
    assert json.loads(reporting.report_json(job_cgroups={'job':'/jobs/j'}, proc_root=tmp_path,
                                          host_pid_namespace_verified=True)) == result


def test_external_pid_prevents_complete_attribution(tmp_path, monkeypatch):
    (tmp_path / '55').mkdir()
    (tmp_path / '55' / 'cgroup').write_text('0::/other\n')
    monkeypatch.setattr(reporting, 'collect_process_snapshot', lambda **kw: {
        'gpu_index':0, 'source':'amd-smi-process-json',
        'processes':{55:{'gfx_ns':None, 'memory_bytes':0, 'gpu_index':0}}})
    result = reporting.collect_attribution_report(job_cgroups={'job':'/jobs/j'}, proc_root=tmp_path,
                                                   host_pid_namespace_verified=True)
    assert result['unmatched_pids'] == [55]
    assert result['external_activity_detected']
    assert not result['attribution_verified']
    assert not result['billing_eligible']
