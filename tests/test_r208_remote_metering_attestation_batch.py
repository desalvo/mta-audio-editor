"""Remote worker metering integrity matrix (offline; no ROCm certification)."""
import copy
import math

import pytest

from app import ai_remote_metering_attestation as a

KEY = b'worker-scoped-demo-key-0123456789-abcdefghijklmnopqrstuvwxyz'
BASE = dict(job_id='job_123', request_id='request_123', worker_id='worker_123',
            usage={'cpu_seconds': 3.2, 'read_bytes': 100, 'write_bytes': 200})


def signed():
    return a.sign(KEY, **BASE)


def test_valid_roundtrip():
    assert a.verify(KEY, signed(), job_id=BASE['job_id'], request_id=BASE['request_id'],
                    worker_id=BASE['worker_id']) == BASE['usage']


@pytest.mark.parametrize('field,value', [
    ('job_id',''), ('job_id','a b'), ('job_id','a/b'), ('job_id','a'*129),
    ('job_id',None), ('job_id',123), ('job_id','é'), ('job_id','a\n'),
    ('request_id',''), ('request_id','a b'), ('request_id','a/b'),
    ('request_id','a'*129), ('request_id',None), ('request_id',123),
    ('request_id','é'), ('request_id','a\n'),
    ('worker_id',''), ('worker_id','a b'), ('worker_id','a/b'),
    ('worker_id','a'*129), ('worker_id',None), ('worker_id',123),
    ('worker_id','é'), ('worker_id','a\n'),
])
def test_reject_bad_identity(field, value):
    body = dict(BASE)
    body[field] = value
    with pytest.raises(ValueError):
        a.sign(KEY, **body)


@pytest.mark.parametrize('usage', [
    {}, None, [], {'gpu_seconds':1}, {'cpu_seconds':True},
    {'cpu_seconds':False}, {'cpu_seconds':-1}, {'cpu_seconds':float('inf')},
    {'cpu_seconds':float('-inf')}, {'cpu_seconds':float('nan')},
    {'cpu_seconds':'1'}, {'cpu_seconds':None}, {'cpu_seconds':1e20},
    {'cpu_seconds':3, 'read_bytes':0.5},
    {'cpu_seconds':3, 'write_bytes':-1},
    {'cpu_seconds':3, 'read_bytes':2**54},
    {'cpu_seconds':3, 'write_bytes':True},
    {'cpu_seconds':3, 'gpu_energy_joules':12},
    {'cpu_seconds':3, 'unexpected':7},
    {'read_bytes':10},
])
def test_reject_bad_usage(usage):
    with pytest.raises(ValueError):
        a.sign(KEY, **{**BASE, 'usage':usage})


@pytest.mark.parametrize('field,value', [
    ('signature',''), ('signature','f'*63), ('signature','f'*65),
    ('signature','z'*64), ('signature','A'*64), ('signature',None),
    ('schema_version',0), ('schema_version',2), ('schema_version',True),
    ('job_id','otherjob'), ('request_id','otherrequest'),
    ('worker_id','otherworker'),
])
def test_reject_tampered_envelope(field, value):
    envelope = signed()
    envelope[field] = value
    with pytest.raises(ValueError):
        a.verify(KEY, envelope, job_id=BASE['job_id'], request_id=BASE['request_id'],
                 worker_id=BASE['worker_id'])


def test_reject_usage_tampering():
    envelope = signed()
    envelope['usage']['cpu_seconds'] = 4.2
    with pytest.raises(ValueError):
        a.verify(KEY, envelope, job_id=BASE['job_id'], request_id=BASE['request_id'],worker_id=BASE['worker_id'])


def test_reject_extra_schema_fields():
    envelope = signed()
    envelope['gpu_usage'] = 1
    with pytest.raises(ValueError):
        a.verify(KEY, envelope, job_id=BASE['job_id'], request_id=BASE['request_id'],worker_id=BASE['worker_id'])


def test_reject_replayed_job_identity():
    with pytest.raises(ValueError):
        a.verify(KEY, signed(), job_id='different',request_id=BASE['request_id'],worker_id=BASE['worker_id'])


def test_reject_short_signing_key():
    with pytest.raises(ValueError):
        a.sign(b'short', **BASE)


def test_reject_wrong_verification_key():
    with pytest.raises(ValueError):
        a.verify(b'x'*32, signed(), job_id=BASE['job_id'],request_id=BASE['request_id'],worker_id=BASE['worker_id'])
