import pytest
from app.ai_gpu_process_meter import pid_engine_ns, cgroup_gpu_snapshot


def test_drm_gpu_per_pid_deduplicates_fds_and_separates_clients(tmp_path):
    directory = tmp_path / '123' / 'fdinfo'
    directory.mkdir(parents=True)
    for fd, cid, ns in [('4', '8', 500), ('5', '8', 500), ('6', '9', 200)]:
        (directory / fd).write_text('drm-driver: amdgpu\ndrm-client-id: '+cid+'\n'
                                     + f'drm-engine-compute: {ns} ns\n')
    assert pid_engine_ns(123, proc_root=tmp_path) == {'compute': 700}


def test_gpu_diagnostics_ignore_non_drm_host_counters(tmp_path):
    d = tmp_path / '123' / 'fdinfo'
    d.mkdir(parents=True)
    (d / '3').write_text('drm-engine-compute: 99999 ns\n')
    assert pid_engine_ns(123, proc_root=tmp_path) == {}


def test_cgroup_snapshot_scopes_pids_to_job(tmp_path):
    cg, proc = tmp_path / 'cg', tmp_path / 'proc'
    cg.mkdir()
    (cg / 'cgroup.procs').write_text('123\n')
    (proc / '123' / 'fdinfo').mkdir(parents=True)
    (proc / '123' / 'fdinfo' / '4').write_text('drm-driver: amdgpu\ndrm-client-id: 1\ndrm-engine-gfx: 123 ns\n')
    assert cgroup_gpu_snapshot(cg, proc_root=proc) == {123: {'gfx': 123}}


def test_missing_process_fails_closed(tmp_path):
    cg = tmp_path / 'cg'
    cg.mkdir()
    (cg / 'cgroup.procs').write_text('999\n')
    with pytest.raises(RuntimeError, match='exited'):
        cgroup_gpu_snapshot(cg, proc_root=tmp_path / 'proc')
