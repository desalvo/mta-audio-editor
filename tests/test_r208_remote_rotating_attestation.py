import copy
from unittest.mock import patch
import pytest
from app import ai_remote_metering_attestation as m, ai_metering_bridge as b

K1=b'a'*32
K2=b'b'*32
ARGS={'job_id':'j123','request_id':'r123','worker_id':'w123','usage':{'cpu_seconds':1.25,'read_bytes':123}}

def issued():
    return m.sign_rotating(K1,key_id='active',**ARGS)

def test_roundtrip_and_revocation():
    signed=issued()
    assert m.verify_rotating({'active':K1},signed,**{k:ARGS[k] for k in ('job_id','request_id','worker_id')}) == ARGS['usage']
    with pytest.raises(ValueError):
        m.verify_rotating({'new':K2},signed,**{k:ARGS[k] for k in ('job_id','request_id','worker_id')})

def test_rotation_allows_two_distinct_keys():
    a=issued()
    z=m.sign_rotating(K2,key_id='new',**ARGS)
    ids={k:ARGS[k] for k in ('job_id','request_id','worker_id')}
    assert m.verify_rotating({'active':K1,'new':K2},a,**ids)==ARGS['usage']
    assert m.verify_rotating({'active':K1,'new':K2},z,**ids)==ARGS['usage']

@pytest.mark.parametrize('name,value',[
    ('key_id','new'),('key_id',''),('key_id','a/b'),('key_id','A'*65),
    ('job_id','fake'),('request_id','fake'),('worker_id','fake'),
    ('schema_version',1),('schema_version',True),('schema_version',3),
    ('signature','0'*64),('signature',''),('signature','f'*63),('signature',None),
    ('usage',{}),('usage',{'gpu_seconds':1}),('usage',{'cpu_seconds':-1}),
    ('usage',{'cpu_seconds':float('nan')}),('usage',{'cpu_seconds':True}),
    ('usage',{'cpu_seconds':1,'write_bytes':1.0}),
    ('usage',{'cpu_seconds':1,'read_bytes':2**54}),
    ('usage',{'cpu_seconds':1,'extra':2}),
    ('usage',{'cpu_seconds':1e16}),('usage',None),
    ('usage',{'cpu_seconds':'3'}),('usage',{'cpu_seconds':float('inf')}),
    ('key_id',None),('key_id',4),('job_id',None),('request_id',None),
    ('worker_id',None),('signature','F'*64),('signature',False),
])
def test_tampered_field_rejected(name,value):
    e=issued();e[name]=value
    ids={k:ARGS[k] for k in ('job_id','request_id','worker_id')}
    with pytest.raises(ValueError):m.verify_rotating({'active':K1},e,**ids)

@pytest.mark.parametrize('extra',[None,0,False,[],{},b'bad',{'active':b'a'}, {'active':'a'*32}, {'other':K1}])
def test_bad_keyring_rejected(extra):
    ids={k:ARGS[k] for k in ('job_id','request_id','worker_id')}
    with pytest.raises(ValueError):m.verify_rotating(extra,issued(),**ids)

@pytest.mark.parametrize('candidate',['','a/b','\x00','a'*65,10,None,' a','a.b'])
def test_invalid_key_ids(candidate):
    with pytest.raises(ValueError):m.sign_rotating(K1,key_id=candidate,**ARGS)

def test_bridge_captures_only_verified_values():
    with patch.object(b,'_identity',return_value=(1,'arranger')),patch.object(b,'capture',return_value=True) as cap:
        assert b.capture_rotating_remote('j123',issued(),request_id='r123',worker_id='w123',keyring={'active':K1})
        cap.assert_called_once_with('j123',ARGS['usage'],'remote-worker')

def test_bridge_rejects_wrong_worker_without_write():
    with patch.object(b,'_identity',return_value=(1,'arranger')),patch.object(b,'capture') as cap:
        with pytest.raises(ValueError):b.capture_rotating_remote('j123',issued(),request_id='r123',worker_id='someone_else',keyring={'active':K1})
        cap.assert_not_called()
