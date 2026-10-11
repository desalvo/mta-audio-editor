import pytest
from app.ai_gpu_process_meter import pid_gpu_sample, cgroup_gpu_detailed_snapshot


def test_real_gpu_engine_and_resident_memory_per_client(tmp_path):
    directory = tmp_path / 'proc' / '123' / 'fdinfo'
    directory.mkdir(parents=True)
    sample = ('drm-driver: amdgpu\ndrm-client-id: 5\n'
              'drm-engine-compute: 250 ns\ndrm-memory-vram: 800 KiB\n'
              'drm-resident-vram: 600 KiB\n')
    (directory / '3').write_text(sample)
    (directory / '4').write_text(sample)  # duplicate FD cannot double charge
    (directory / '5').write_text(sample.replace('drm-client-id: 5', 'drm-client-id: 6'))
    result = pid_gpu_sample(123, proc_root=tmp_path / 'proc')
    assert result.engine_ns == {'compute': 500}
    assert result.memory_kib == {'memory-vram': 1600, 'resident-vram': 1200}


def test_only_job_cgroup_members_are_observed(tmp_path):
    cg = tmp_path / 'cg'
    cg.mkdir()
    (cg / 'cgroup.procs').write_text('42')
    fd = tmp_path / 'proc' / '42' / 'fdinfo'
    fd.mkdir(parents=True)
    (fd / '9').write_text('drm-driver: i915\ndrm-client-id: 7\ndrm-engine-render: 100 ns')
    assert cgroup_gpu_detailed_snapshot(cg, proc_root=tmp_path / 'proc')[42].engine_ns == {'render': 100}


def test_exited_gpu_process_does_not_create_billing_value(tmp_path):
    cg = tmp_path / 'cg'
    cg.mkdir()
    (cg / 'cgroup.procs').write_text('42')
    with pytest.raises(RuntimeError, match='exited'):
        cgroup_gpu_detailed_snapshot(cg, proc_root=tmp_path / 'proc')
