import json
import pytest
from app import ai_gpu_diagnostic_session as session
from app.ai_amd_smi_collector import GPUAttributionError


def _result(job='job', external=False):
    return {'schema':'mta-gpu-attribution-diagnostic-v1', 'processes':[
        {'job_id': job, 'host_pid': 50}], 'external_activity_detected': external,
        'attribution_verified': not external, 'billing_eligible':False,
        'measured_gpu_seconds':None}


def test_session_with_external_activity(tmp_path, monkeypatch):
    inputs = iter([_result(), _result(external=True), _result()])
    monkeypatch.setattr(session, 'collect_attribution_report', lambda **kw: next(inputs))
    pauses = []
    report = session.collect_session(job_cgroups={'job':'/jobs/x'}, samples=3,
        interval_seconds=0.1, host_pid_namespace_verified=True, sleep=pauses.append,
        clock=iter([1., 2., 3.]).__next__)
    assert pauses == [0.1, 0.1]
    assert report['external_activity_detected']
    assert not report['attribution_verified_in_all_samples']
    assert report['observed_jobs'] == ['job']
    assert report['billing_eligible'] is False
    assert report['measured_gpu_seconds'] is None
    dest = tmp_path / 'report.json'
    session.write_session_report(dest, report)
    assert json.loads(dest.read_text()) == report
    assert dest.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize('samples,interval', [(0,0), (101,0), (True,0), (1,-1), (1,float('nan')), (1,float('inf'))])
def test_invalid_sample_parameters(samples, interval):
    with pytest.raises(GPUAttributionError):
        session.collect_session(job_cgroups={}, samples=samples, interval_seconds=interval,
                                host_pid_namespace_verified=True)


def test_unverified_host_does_not_sample(monkeypatch):
    monkeypatch.setattr(session, 'collect_attribution_report', lambda **kw: pytest.fail('sampled'))
    with pytest.raises(GPUAttributionError):
        session.collect_session(job_cgroups={})


def test_refuse_billable_export(tmp_path):
    with pytest.raises(GPUAttributionError):
        session.write_session_report(tmp_path/'report.json', {'schema':'mta-gpu-diagnostic-session-v1',
            'billing_eligible': True, 'measured_gpu_seconds': 10})
    assert not (tmp_path/'report.json').exists()
