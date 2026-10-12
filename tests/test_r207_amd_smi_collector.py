"""GPU collection and mapping fail closed for host/LXC mismatch."""
import json
from pathlib import Path

import pytest

from app.ai_amd_smi_collector import (
    GPUAttributionError, correlate_processes, diagnostic_window, parse_process_json,
)
from app.ai_gpu_shared_estimator import estimate_shared_capacity


def sample(pids=(1648234, 21729)):
    return json.dumps([{'gpu': 0, 'process_list': [
        {'process_info': {'pid': pid, 'mem_usage': {'value': 23688085504, 'unit': 'B'},
                          'usage': {'gfx': {'value': 0, 'unit': 'ns'}}}}
        for pid in pids]}])


def test_sample_from_real_lxc_format():
    snapshot = parse_process_json(sample())
    assert snapshot['processes'][1648234]['memory_bytes'] == 23688085504
    assert snapshot['processes'][1648234]['gfx_ns'] == 0
    assert not snapshot['billing_eligible']


def test_host_pid_cannot_be_guessed_from_container_proc(tmp_path: Path):
    proc = tmp_path / 'proc'
    (proc / '1648234').mkdir(parents=True)
    (proc / '1648234' / 'cgroup').write_text('0::/system.slice/mta/job-a\n')
    snap = parse_process_json(sample((1648234,)))
    result = correlate_processes(snap, job_cgroups={'a': '/system.slice/mta/job-a'},
                                 proc_root=proc)
    assert result['unknown_host_pids'] == [1648234]
    assert not result['attribution_verified']
    assert not result['billing_eligible']


def test_verified_host_cgroup_and_nested_children(tmp_path: Path):
    proc = tmp_path / 'hostproc'
    (proc / '1648234').mkdir(parents=True)
    (proc / '1648234' / 'cgroup').write_text('0::/system.slice/mta/job-a/worker\n')
    snap = parse_process_json(sample((1648234,)))
    result = correlate_processes(snap, job_cgroups={'a': '/system.slice/mta/job-a'},
                                 proc_root=proc, host_pid_namespace_verified=True)
    assert result['host_pid_to_job'] == {1648234: 'a'}
    assert result['attribution_verified']


def test_external_process_prevents_allocation(tmp_path: Path):
    proc = tmp_path / 'hostproc'
    (proc / '1648234').mkdir(parents=True)
    (proc / '1648234' / 'cgroup').write_text('0::/system.slice/mta/job-a\n')
    snap = parse_process_json(sample())
    result = correlate_processes(snap, job_cgroups={'a': '/system.slice/mta/job-a'},
                                 proc_root=proc, host_pid_namespace_verified=True)
    window = diagnostic_window(start=0, end=10, utilization=1,
                               job_weights={'a': 8}, correlation=result)
    estimate = estimate_shared_capacity([window], device_id='0')
    assert result['unknown_host_pids'] == [21729]
    assert estimate['allocated_capacity_seconds'] == 0


def test_unverified_pid_blocks_estimate_even_with_100_utilization():
    snap = parse_process_json(sample((1648234,)))
    corr = correlate_processes(snap, job_cgroups={'a': '/mta/job-a'})
    window = diagnostic_window(start=0, end=10, utilization=1,
                               job_weights={'a': 8.414}, correlation=corr)
    assert estimate_shared_capacity([window], device_id='0')['job_estimates'] == {}


@pytest.mark.parametrize('payload', [
    '{}', '[{"gpu":0,"process_list":null}]', 'invalid',
    '[{"gpu":1,"process_list":[]}]',
    '[{"gpu":0,"process_list":[{"process_info":{"pid":0}}]}]',
    '[{"gpu":0,"process_list":[{"process_info":{"pid":2}}, {"process_info":{"pid":2}}]}]',
])
def test_malformed_snapshots_rejected(payload):
    with pytest.raises(GPUAttributionError):
        parse_process_json(payload)


def test_cgroup_prefix_boundary(tmp_path: Path):
    (tmp_path / '2').mkdir()
    (tmp_path / '2' / 'cgroup').write_text('0::/mta/job-ab\n')
    result = correlate_processes(parse_process_json(sample((2,))),
                                 job_cgroups={'a': '/mta/job-a'}, proc_root=tmp_path,
                                 host_pid_namespace_verified=True)
    assert result['unknown_host_pids'] == [2]
