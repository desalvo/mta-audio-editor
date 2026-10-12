"""Fail-closed shared GPU allocation; no monetary ledger writes."""
import pytest

from app.ai_gpu_shared_estimator import estimate_shared_capacity


def win(start=0, end=10, utilization=1, jobs=None, external_activity=False):
    return {'start': start, 'end': end, 'utilization': utilization,
            'jobs': {'a': 8.414, 'b': 8.422} if jobs is None else jobs,
            'external_activity': external_activity}


def test_two_concurrent_jobs_conserve_capacity():
    result = estimate_shared_capacity([win()], device_id='8060S')
    assert result['billing_eligible'] is False
    assert sum(result['job_estimates'].values()) == pytest.approx(10)
    assert result['job_estimates']['a'] == pytest.approx(4.9976, abs=0.001)
    assert result['job_estimates']['b'] == pytest.approx(5.0024, abs=0.001)


def test_utilization_scales_and_idle_not_charged():
    result = estimate_shared_capacity([win(utilization=0.4)], device_id='8060S')
    assert result['allocated_capacity_seconds'] == pytest.approx(4)


def test_external_process_blocks_allocation():
    result = estimate_shared_capacity([win(external_activity=True)], device_id='8060S')
    assert result['job_estimates'] == {}
    assert result['unallocated_capacity_seconds'] == pytest.approx(10)


def test_missing_utilization_is_not_assumed_full():
    result = estimate_shared_capacity([win(utilization=None)], device_id='8060S')
    assert result['job_estimates'] == {}
    assert result['skipped_windows'] == 1


def test_no_weight_no_allocation():
    result = estimate_shared_capacity([win(jobs={'a': 0, 'b': 0})], device_id='8060S')
    assert result['allocated_capacity_seconds'] == 0


def test_disjoint_windows_sum_without_overlap():
    result = estimate_shared_capacity([win(end=2, jobs={'a': 1}),
                                      win(start=2, end=4, jobs={'b': 1})], device_id='8060S')
    assert result['job_estimates'] == {'a': 2, 'b': 2}


@pytest.mark.parametrize('bad', [
    [win(start=2, end=1)],
    [win(), win(start=9, end=12)],
    [win(utilization=1.1)],
    [win(jobs={'a': -1})],
    [win(jobs={'a': float('nan')})],
    [win(external_activity=None)],
])
def test_invalid_data_rejected(bad):
    with pytest.raises(ValueError):
        estimate_shared_capacity(bad, device_id='8060S')
