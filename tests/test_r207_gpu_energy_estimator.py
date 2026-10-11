import pytest
from app.ai_gpu_energy_estimator import EnergyCalibration, estimate_job_energy


def test_incremental_job_only():
    profile = EnergyCalibration('GPU-1', 40, 240)
    result = estimate_job_energy(profile, gpu_engine_seconds=10, job_wall_seconds=20,
                                 exclusive_gpu=True, complete_lifecycle=True)
    assert result['estimated_energy_joules'] == 2000
    assert not result['billing_eligible']
    assert result['kind'] == 'estimated_not_measured'


def test_total_includes_idle_during_job_only():
    result = estimate_job_energy(EnergyCalibration('GPU-1', 40, 240), gpu_engine_seconds=10,
                                 job_wall_seconds=20, exclusive_gpu=True,
                                 complete_lifecycle=True, baseline_policy='total')
    assert result['estimated_energy_joules'] == 2800


@pytest.mark.parametrize('exclusive,complete', [(False, True), (True, False), (False, False)])
def test_incomplete_or_shared_not_attributable(exclusive, complete):
    result = estimate_job_energy(EnergyCalibration('GPU-1', 40, 240), gpu_engine_seconds=10,
                                 job_wall_seconds=20, exclusive_gpu=exclusive,
                                 complete_lifecycle=complete)
    assert result['estimated_energy_joules'] is None


def test_reject_double_counted_engines():
    with pytest.raises(ValueError, match='Overlapping'):
        estimate_job_energy(EnergyCalibration('GPU-1', 40, 240), gpu_engine_seconds=30,
                            job_wall_seconds=10, exclusive_gpu=True, complete_lifecycle=True)


def test_reject_bad_power_calibration():
    with pytest.raises(ValueError, match='exceed'):
        estimate_job_energy(EnergyCalibration('GPU-1', 240, 240), gpu_engine_seconds=1,
                            job_wall_seconds=2, exclusive_gpu=True, complete_lifecycle=True)
