"""Fail-closed accounting for nested cgroup members and delegated controllers."""
from pathlib import Path
import pytest
from app.ai_cgroup_metering import _assert_empty


def test_recursive_cgroup_occupancy_is_rejected(tmp_path: Path):
    (tmp_path / 'cgroup.events').write_text('populated 1\nfrozen 0\n')
    (tmp_path / 'cgroup.procs').write_text('')
    with pytest.raises(RuntimeError, match='contains processes'):
        _assert_empty(tmp_path)


def test_empty_recursive_cgroup_is_valid(tmp_path: Path):
    (tmp_path / 'cgroup.events').write_text('populated 0\nfrozen 0\n')
    _assert_empty(tmp_path)


def test_missing_cgroup_occupancy_is_not_accepted(tmp_path: Path):
    (tmp_path / 'cgroup.events').write_text('frozen 0\n')
    with pytest.raises(RuntimeError):
        _assert_empty(tmp_path)
