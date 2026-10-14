"""Broad integration boundary matrix for operator-provisioned rotating keys."""
import json
from unittest.mock import patch
import pytest
from app import ai_remote_keyring as ring
from app import ai_remote_metering_attestation as signing
from app import ai_metering_bridge as bridge

A = 'ab' * 32
B = 'cd' * 32
GOOD = json.dumps({'old': A, 'new': B})
IDENTITY = dict(job_id='job55', request_id='req55', worker_id='worker55')


def test_operator_rotation_and_revocation(monkeypatch):
    envelope = signing.sign_rotating(bytes.fromhex(A), key_id='old', usage={'cpu_seconds':1.2}, **IDENTITY)
    monkeypatch.setenv('MTA_AI_REMOTE_METERING_KEYS_JSON', GOOD)
    assert signing.verify_rotating(ring.active_keyring(), envelope, **IDENTITY) == {'cpu_seconds':1.2}
    monkeypatch.setenv('MTA_AI_REMOTE_METERING_KEYS_JSON', json.dumps({'new':B}))
    with pytest.raises(ValueError):
        signing.verify_rotating(ring.active_keyring(), envelope, **IDENTITY)


def test_never_expose_secret_or_key_id(monkeypatch):
    monkeypatch.setenv('MTA_AI_REMOTE_METERING_KEYS_JSON', GOOD)
    data = ring.public_status()
    assert data['configured'] and data['active_key_count'] == 2
    assert 'old' not in str(data) and A not in str(data)


@pytest.mark.parametrize('value', [None, '', ' ', '{}', '[]', 'null', 'true', '42', '"string"', '{bad',
    '{"a":"%s","a":"%s"}' % (A,B),
    json.dumps({'bad key': A}), json.dumps({'':A}), json.dumps({'x'*65:A}),
    json.dumps({'a':A.upper()}), json.dumps({'a':A[:-1]}), json.dumps({'a':'a'*65}),
    json.dumps({'a':'0'*64,'b':'0'*64}), json.dumps({'a': True}), json.dumps({'a':42}),
    json.dumps({'a': None}), json.dumps({'a': []}), json.dumps({'a': {}}),
    json.dumps({str(i):A for i in range(33)}), ' ' * 32769,
])
def test_invalid_configuration(value):
    with pytest.raises(ValueError): ring.decode_keyring(value)


@pytest.mark.parametrize('key_id', ['a', 'key_1', 'Z-2', 'z'*64])
def test_valid_key_names(key_id):
    assert ring.decode_keyring(json.dumps({key_id:A}))[key_id] == bytes.fromhex(A)


@pytest.mark.parametrize('bad_id', ['.', '/', '\\', ' ', '\t', '\n', '\x00', 'ö', '€',
    '!', '@', '#', '$', '%', '^', '&', '*', '(', ')', '+', '=', '[', ']', '{', '}', ':',
    ';', ',', '<', '>', '?', '|', '~', '`', 'a'*65, '\u202e', '\u200b'])
def test_reject_unsafe_key_identifiers(bad_id):
    with pytest.raises(ValueError): ring.decode_keyring(json.dumps({bad_id:A}))


@pytest.mark.parametrize('key', ['G'*64,'A'*64,'zz'*32,'aa'*31+'xx','ff'*31+'f','😀'*32,
    '\n'*64,'00'*31,'aa'*129,'aa'*16, 'ab '*32, 'ab\t'*32, 'a'*63, 'a'*257])
def test_reject_invalid_key_material(key):
    with pytest.raises(ValueError): ring.decode_keyring(json.dumps({'key':key}))


@pytest.mark.parametrize('usage', [
    {'cpu_seconds':0}, {'cpu_seconds':1}, {'cpu_seconds':1.5},
    {'cpu_seconds':1,'read_bytes':0}, {'cpu_seconds':1,'write_bytes':2},
    {'cpu_seconds':1,'read_bytes':2,'write_bytes':3},
])
def test_capture_v2_with_operator_keyring(monkeypatch, usage):
    monkeypatch.setenv('MTA_AI_REMOTE_METERING_KEYS_JSON', GOOD)
    envelope = signing.sign_rotating(bytes.fromhex(A), key_id='old', usage=usage, **IDENTITY)
    with patch.object(bridge, '_identity', return_value=(1,'arranger')), patch.object(bridge, 'capture', return_value=True) as capture:
        assert bridge.capture_rotating_remote('job55', envelope, request_id='req55', worker_id='worker55', keyring=ring.active_keyring())
        capture.assert_called_once_with('job55', usage, 'remote-worker')


def test_unavailable_status_is_safe(monkeypatch):
    monkeypatch.delenv('MTA_AI_REMOTE_METERING_KEYS_JSON', raising=False)
    assert ring.public_status() == {'configured':False, 'status':'unavailable'}


@pytest.mark.parametrize('wrong_field,wrong_value', [
    ('job_id','other'), ('request_id','other'), ('worker_id','other'),
    ('job_id',''), ('request_id',''), ('worker_id',''),
    ('job_id',None), ('request_id',None), ('worker_id',None),
    ('job_id',42), ('request_id',42), ('worker_id',42),
])
def test_operator_capture_rejects_unbound_identity(monkeypatch, wrong_field, wrong_value):
    monkeypatch.setenv('MTA_AI_REMOTE_METERING_KEYS_JSON', GOOD)
    signed = signing.sign_rotating(bytes.fromhex(A), key_id='old',
                                   usage={'cpu_seconds':1}, **IDENTITY)
    supplied = dict(IDENTITY)
    supplied[wrong_field] = wrong_value
    with patch.object(bridge, '_identity', return_value=(1,'arranger')), patch.object(bridge,'capture') as cap:
        with pytest.raises(ValueError):
            bridge.capture_operator_authenticated_remote('job55', signed,
                request_id=supplied['request_id'], worker_id=supplied['worker_id']) if wrong_field != 'job_id' else bridge.capture_operator_authenticated_remote(wrong_value, signed,request_id='req55',worker_id='worker55')
        cap.assert_not_called()


def test_operator_capture_uses_current_keyring(monkeypatch):
    signed = signing.sign_rotating(bytes.fromhex(A), key_id='old',usage={'cpu_seconds':2},**IDENTITY)
    monkeypatch.setenv('MTA_AI_REMOTE_METERING_KEYS_JSON', GOOD)
    with patch.object(bridge,'_identity',return_value=(3,'arranger')),patch.object(bridge,'capture',return_value=True) as cap:
        assert bridge.capture_operator_authenticated_remote('job55',signed,request_id='req55',worker_id='worker55')
        cap.assert_called_once()
    monkeypatch.setenv('MTA_AI_REMOTE_METERING_KEYS_JSON',json.dumps({'new':B}))
    with patch.object(bridge,'_identity',return_value=(3,'arranger')),patch.object(bridge,'capture') as cap:
        with pytest.raises(ValueError):
            bridge.capture_operator_authenticated_remote('job55',signed,request_id='req55',worker_id='worker55')
        cap.assert_not_called()
