"""Finalization must never silently coerce malformed explicit telemetry."""
import pytest
from app import ai_billing


@pytest.mark.parametrize('invalid', [[], False, '', 0, {'cpu_seconds': float('nan')},
                                      {'cpu_seconds': float('inf')},
                                      {'cpu_seconds': 10 ** 1000},
                                      {'cpu_seconds': -1},
                                      {'gpu_slot_seconds_estimated': 1}])
@pytest.mark.parametrize('finalizer', [ai_billing.finish_job, ai_billing.finish_job_idempotent])
def test_malformed_telemetry_rejected_before_ledger_access(invalid, finalizer):
    with pytest.raises(ValueError):
        finalizer('not-a-job', 'done', invalid, source='worker')


def test_valid_zero_and_none_telemetry():
    assert ai_billing._validate_usage({}) == {}
    assert ai_billing._validate_usage({'cpu_seconds': 0}) == {'cpu_seconds': 0.0}
