"""Actual isolated SAM entrypoint with synthetic libraries, never real weights."""
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
from app.ai_cgroup_metering import _worker_failure, safe_failure_metadata
from app.sam_audio_worker import _failure_reason

ROOT=Path(__file__).resolve().parents[1]
BOOTSTRAP=r'''
import contextlib,os,runpy,sys,types
sys.path.insert(0,os.environ['TEST_REPO'])
from app import model_license_policy,sam_audio_compat
model_license_policy.evaluate_model=lambda *_:None
sam_audio_compat.sam_hub_compat=contextlib.nullcontext
mode=os.environ.get('TEST_SAM_MODE','ok')
class Model:
 @classmethod
 def from_pretrained(cls,name):
  if mode=='gated':raise type('GatedRepoError',(Exception,),{})('PRIVATE hf_secret')
  return cls()
 def eval(self):return self
 def to(self,device):
  if mode=='oom':raise type('OutOfMemoryError',(Exception,),{})('PRIVATE GPU detail')
  return self
 def separate(self,*args,**kwargs):return types.SimpleNamespace(target=Audio())
class Audio:
 ndim=2
 def detach(self):return self
 def cpu(self):return self
class Processor:
 audio_sampling_rate=48000
 @classmethod
 def from_pretrained(cls,name):return cls()
 def __call__(self,**kwargs):return self
 def to(self,device):return self
sys.modules['torch']=types.SimpleNamespace(cuda=types.SimpleNamespace(is_available=lambda:True),inference_mode=contextlib.nullcontext)
sys.modules['torchaudio']=types.SimpleNamespace(save=lambda path,audio,rate:open(path,'wb').write(b'FAKE-WAV'))
sys.modules['sam_audio']=types.SimpleNamespace(SAMAudio=Model,SAMAudioProcessor=Processor)
sys.argv=['sam_audio_worker.py','--source','input.wav','--output',os.environ['TEST_OUTPUT'],
          '--model','facebook/sam-audio-small','--prompt','drums']
runpy.run_path(os.environ['TEST_RUNNER'],run_name='__main__')
'''


def run_worker(tmp_path,mode):
    env={**os.environ,'TEST_REPO':str(ROOT),'TEST_RUNNER':str(ROOT/'app/sam_audio_worker.py'),
         'TEST_OUTPUT':str(tmp_path/'out.wav'),'TEST_SAM_MODE':mode}
    return subprocess.run([sys.executable,'-I','-c',BOOTSTRAP],cwd=tmp_path,env=env,
                          text=True,capture_output=True,check=False,timeout=10)


def test_isolated_worker_imports_installed_bridge_and_reaches_inference(tmp_path):
    result=run_worker(tmp_path,'ok')
    assert result.returncode==0,result.stderr
    assert (tmp_path/'out.wav').read_bytes()==b'FAKE-WAV'


@pytest.mark.parametrize('mode,category',[('gated','sam_checkpoint_access_denied'),('oom','sam_insufficient_memory')])
def test_worker_failure_keeps_safe_specific_diagnosis_through_nested_traceback(tmp_path,mode,category):
    result=run_worker(tmp_path,mode)
    assert result.returncode!=0
    failure=_worker_failure(result.stderr+'\nsubprocess.CalledProcessError: PRIVATE nested detail',1)
    safe=safe_failure_metadata(failure)
    assert safe['category']==category
    assert 'PRIVATE' not in json.dumps(safe)
    assert 'PRIVATE' not in json.dumps(failure)


@pytest.mark.parametrize('name,status,expected',[
    ('GatedRepoError',None,'checkpoint_access_denied'),
    ('HfHubHTTPError',401,'checkpoint_access_denied'),
    ('HfHubHTTPError',403,'checkpoint_access_denied'),
    ('HfHubHTTPError',404,'checkpoint_not_found_or_inaccessible'),
    ('RepositoryNotFoundError',None,'checkpoint_not_found_or_inaccessible'),
    ('HfHubHTTPError',429,'hub_rate_limited'),
    ('LocalEntryNotFoundError',None,'hub_unavailable_or_cache_missing'),
    ('ConnectTimeout',None,'hub_unavailable_or_cache_missing'),
    ('SafetensorError',None,'checkpoint_format_invalid'),
    ('OutOfMemoryError',None,'insufficient_memory'),
    ('RuntimeError',None,None),
])
def test_failure_reason_uses_known_type_and_status_only(name,status,expected):
    error=type(name,(Exception,),{})('PRIVATE credential and message')
    error.response=SimpleNamespace(status_code=status)
    outer=RuntimeError('PRIVATE outer');outer.__cause__=error
    assert _failure_reason(outer)==expected


def test_unknown_model_failure_does_not_guess_access_or_gpu():
    failure=_worker_failure('MTA_SAM_FAILURE:model_load\nRuntimeError: PRIVATE',1)
    assert failure['category']=='sam_model_load_failed'
    assert 'PRIVATE' not in json.dumps(safe_failure_metadata(failure))


def test_rocm_runtime_out_of_memory_is_classified_without_disclosing_details():
    assert _failure_reason(RuntimeError('HIP out of memory; PRIVATE path'))=='insufficient_memory'
