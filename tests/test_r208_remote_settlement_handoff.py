import pytest
from app import ai_metering_bridge as bridge


def test_remote_settlement_occurs_before_result_release(monkeypatch):
    calls = []
    monkeypatch.setattr(bridge, 'infer_durable_remote', lambda *a, **k: (b'RIFFpayload', 'audio/wav', 'remote-01'))
    monkeypatch.setattr(bridge, 'register_settlement', lambda job: calls.append(job))
    assert bridge.infer_and_register_remote_settlement('local-01', base_url='x', token='t', wav=b'a', worker_id='w')[2] == 'remote-01'
    assert calls == ['local-01']


@pytest.mark.parametrize('reply', [None, (), (b'', 'audio/wav', 'r'), (b'x', 'application/json', 'r'),
                                  (b'x', 'audio/wav', ''), ('x', 'audio/wav', 'r')])
def test_invalid_remote_result_does_not_settle(monkeypatch, reply):
    monkeypatch.setattr(bridge, 'infer_durable_remote', lambda *a, **k: reply)
    monkeypatch.setattr(bridge, 'register_settlement', lambda job: pytest.fail('unexpected settlement'))
    with pytest.raises(ValueError):
        bridge.infer_and_register_remote_settlement('local-01', base_url='x', token='t', wav=b'a', worker_id='w')


def test_remote_settlement_failure_withholds_audio(monkeypatch):
    monkeypatch.setattr(bridge, 'infer_durable_remote', lambda *a, **k: (b'RIFFpayload', 'audio/wav', 'remote-01'))
    def broken(_):
        raise ValueError('missing meter evidence')
    monkeypatch.setattr(bridge, 'register_settlement', broken)
    with pytest.raises(ValueError, match='missing meter evidence'):
        bridge.infer_and_register_remote_settlement('local-01', base_url='x', token='t', wav=b'a', worker_id='w')
