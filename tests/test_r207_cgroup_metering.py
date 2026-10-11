
import pytest

from app import ai_cgroup_metering as meter


def test_cgroup_refuses_undelegated_process(tmp_path, monkeypatch):
    monkeypatch.delenv('MTA_AI_CGROUP_PARENT', raising=False)
    with pytest.raises(RuntimeError, match='not configured'):
        meter.run_cgroup_process(['/bin/true'], cwd=str(tmp_path))


def test_cgroup_refuses_non_cgroup_directory(tmp_path):
    with pytest.raises(RuntimeError, match='delegated /sys/fs/cgroup'):
        meter.run_cgroup_process(['/bin/true'], cwd=str(tmp_path), parent=str(tmp_path))


def test_cpu_stat_reads_only_job_group(tmp_path):
    (tmp_path/'cpu.stat').write_text('usage_usec 2500000\nuser_usec 2000000\nsystem_usec 500000\n')
    assert meter._cpu(tmp_path) == 2.5


def test_io_stat_accumulates_only_job_group(tmp_path):
    (tmp_path/'io.stat').write_text('8:0 rbytes=100 wbytes=200 rios=1 wios=2\n8:16 rbytes=60 wbytes=5\n')
    assert meter._io(tmp_path) == (160.,205.)


def test_missing_cpu_stat_rejected(tmp_path):
    (tmp_path/'cpu.stat').write_text('nr_periods 1\n')
    with pytest.raises(RuntimeError, match='usage_usec'):
        meter._cpu(tmp_path)
