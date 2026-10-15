"""The worker must not silently fall back to direct-child metrics when cgroup is required."""

from pathlib import Path

from app import ai_worker_protocol


def test_cgroup_contract_exposes_cancellation():
    from inspect import signature
    from app.ai_cgroup_metering import run_cgroup_process
    assert 'cancel_event' in signature(run_cgroup_process).parameters


def test_worker_cgroup_branch_is_fail_closed():
    source = Path(ai_worker_protocol.__file__).read_text()
    assert "os.getenv('MTA_AI_CGROUP_PARENT')" in source
    assert 'run_cgroup_process(' in source
    assert 'raise WorkerUnavailable(str(exc)) from exc' in source
    assert "metered_usage = dict(measurement.usage)" in source


def test_gpu_never_billed_from_sampled_diagnostics():
    from app.ai_cgroup_metering import run_cgroup_process
    source = Path(run_cgroup_process.__code__.co_filename).read_text()
    assert "'billable': False" in source
    assert "'gpu_seconds':" not in source
