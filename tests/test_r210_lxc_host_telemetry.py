"""LXC must use authenticated, namespace-matched host process telemetry."""
import json
from pathlib import Path
import time
from types import SimpleNamespace
import pytest
from app import ace_gpu_process_meter as meter
from app import ai_proxmox_gpu_agent_client as client
from scripts import mta_proxmox_gpu_agent as agent


def test_lxc_uses_host_and_never_runs_local_smi(monkeypatch):
    monkeypatch.setattr(meter, 'execution_environment', lambda: 'lxc')
    monkeypatch.setattr(meter, '_ace_pid', lambda: 55)
    monkeypatch.setattr(meter, '_process_identity', lambda pid: '1234')
    monkeypatch.setattr(meter, '_cpu_seconds', lambda pid: 1)
    counters = iter([1000000000, 4000000000])
    monkeypatch.setattr(meter, '_host_agent_counter', lambda *a: (next(counters), 'proxmox-host-drm', 'baseline_only'))
    monkeypatch.setattr(meter, '_drm_counter', lambda pid: pytest.fail('host counter is available'))
    monkeypatch.setattr(meter.subprocess, 'run', lambda *a, **k: pytest.fail('SMI inside LXC'))
    m = meter.AceProcessMeter('http://localhost:8001')
    m.sample()
    data = m.sample()
    assert data['gpu_seconds_estimated'] == 3
    assert data['gpu_metrics_source'] == 'proxmox-host-drm'
    assert 'gpu_seconds' not in data


def test_missing_mount_is_reported_without_local_smi(monkeypatch):
    monkeypatch.setattr(meter, 'execution_environment', lambda: 'lxc')
    monkeypatch.setattr(meter, '_ace_pid', lambda: 55)
    monkeypatch.setattr(meter, '_process_identity', lambda pid: '1234')
    monkeypatch.setattr(meter, '_cpu_seconds', lambda pid: 1)
    monkeypatch.setattr(meter, '_host_agent_counter', lambda *a: (None, 'none', 'host_agent_not_configured'))
    monkeypatch.setattr(meter, '_drm_counter', lambda pid: None)
    monkeypatch.setattr(meter.subprocess, 'run', lambda *a, **k: pytest.fail('SMI inside LXC'))
    assert meter.AceProcessMeter('http://localhost:8001').sample()['gpu_metrics_status'] == 'host_agent_not_configured'


@pytest.mark.parametrize('change,expected', [({}, True), ({'namespace_pid':56}, False),
    ({'pid_namespace_inode':901}, False), ({'process_start_ticks':'other'}, False)])
def test_host_namespace_identity_is_required(monkeypatch, change, expected):
    row = {'host_pid':2222,'namespace_pid':55,'pid_namespace_inode':900,
           'process_start_ticks':'1234','drm_engine_ns':2000000000,'gpu':0}
    row.update(change)
    monkeypatch.setattr(client, 'snapshot', lambda: {'available':True,'telemetry':{
        'source':'host-amd-smi','processes':[row]}})
    real_stat = Path.stat
    monkeypatch.setattr(Path, 'stat', lambda p, *a, **k: SimpleNamespace(st_ino=900)
        if str(p) == '/proc/55/ns/pid' else real_stat(p,*a,**k))
    value, source, reason = meter._host_agent_counter(55,'1234')
    assert (value == 2000000000) is expected
    if not expected: assert reason == 'host_agent_mapping_unavailable'


def test_legacy_host_agent_is_not_guessed(monkeypatch):
    monkeypatch.setattr(client,'snapshot', lambda: {'available':True,'telemetry':{
        'source':'host-amd-smi','processes':[{'host_pid':55,'gpu':0,'host_cgroup':'/lxc/130'}]}})
    real_stat = Path.stat
    monkeypatch.setattr(Path, 'stat', lambda p,*a,**k: SimpleNamespace(st_ino=900)
        if str(p) == '/proc/55/ns/pid' else real_stat(p,*a,**k))
    assert meter._host_agent_counter(55,'1234')[2] == 'host_agent_mapping_unavailable'


def test_host_details_deduplicate_drm_descriptors(tmp_path):
    root=tmp_path/'2222';(root/'fdinfo').mkdir(parents=True);(root/'ns').mkdir()
    fields=['S']+['0']*18+['1234']
    (root/'stat').write_text('2222 (ACE process) '+' '.join(fields))
    (root/'status').write_text('NSpid:\t2222\t55\n')
    (root/'ns/pid').write_text('namespace')
    sample='drm-driver: amdgpu\ndrm-client-id: 7\ndrm-pdev: 0000:01:00.0\ndrm-engine-compute: 3000000000 ns\n'
    (root/'fdinfo/4').write_text(sample);(root/'fdinfo/5').write_text(sample)
    data=agent._process_details(2222,proc_root=tmp_path)
    assert data['namespace_pid'] == 55
    assert data['process_start_ticks'] == '1234'
    assert data['drm_engine_ns'] == 3000000000


def test_client_rejects_malformed_optional_identity(monkeypatch):
    payload={'schema':'mta-gpu-host-agent-v1','timestamp':int(time.time()),'billing_eligible':False,
             'processes':[{'host_pid':2,'gpu':0,'namespace_pid':True}]}
    class Connection:
        def __enter__(self): return self
        def __exit__(self,*a): pass
        def settimeout(self,*a): pass
        def connect(self,*a): pass
        def sendall(self,*a): pass
        def recv(self,*a): return json.dumps(payload).encode()+b'\n'
    monkeypatch.setattr(client.socket,'socket',lambda *a: Connection())
    assert client.snapshot(socket_path='/test/agent.sock',token='x'*32)['available'] is False
