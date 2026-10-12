"""Fail-closed acceptance tests for HIP Events diagnostic input."""
import json

import pytest

from app.ai_hip_event_meter import parse_hip_event_sample


REPORT = {
    'job_id': 'a' * 32, 'device_id': 0, 'process_pid': 983932,
    'elapsed_ms': 6942.0, 'event_pairs': 140177,
    'wall_seconds': 10.01, 'synchronized': True,
}


def test_known_hardware_diagnostic_is_not_billable():
    result = parse_hip_event_sample(json.dumps(REPORT), expected_job_id=REPORT['job_id'])
    assert result['gpu_event_elapsed_seconds'] == 6.942
    assert result['billing_eligible'] is False
    assert result['resource_source'] != 'gpu-agent'
    assert 'gpu_seconds' not in result


@pytest.mark.parametrize('field,value', [
    ('elapsed_ms', float('nan')), ('elapsed_ms', -1),
    ('elapsed_ms', float('inf')), ('event_pairs', True),
    ('event_pairs', 0), ('process_pid', 0),
    ('synchronized', False), ('wall_seconds', -1),
])
def test_reject_invalid_sample(field, value):
    with pytest.raises(ValueError):
        parse_hip_event_sample({**REPORT, field: value}, expected_job_id=REPORT['job_id'])


def test_reject_spoofed_job_identity():
    with pytest.raises(ValueError, match='mismatch'):
        parse_hip_event_sample(REPORT, expected_job_id='b' * 32)


def test_reject_unexpected_fields():
    with pytest.raises(ValueError):
        parse_hip_event_sample({**REPORT, 'gpu_seconds': 6942.0}, expected_job_id=REPORT['job_id'])


def test_reject_oversized_payload():
    with pytest.raises(ValueError):
        parse_hip_event_sample(' ' * 8193, expected_job_id=REPORT['job_id'])
