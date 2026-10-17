"""Demucs must be able to save audio before a server runtime is published."""
from pathlib import Path
from types import SimpleNamespace
import importlib.util
import logging
import json

import pytest
from app.ai_cgroup_metering import _worker_failure, safe_failure_metadata

ROOT=Path(__file__).parents[1]


def installer():
    spec=importlib.util.spec_from_file_location('stem_codec_setup', ROOT/'scripts/install_ai_engines.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


@pytest.mark.parametrize('group',['audio','sam'])
@pytest.mark.parametrize('device,codec',[('rocm','0.11.1+cpu'),('cpu','0.17.0+cpu')])
def test_all_cpu_rocm_groups_pin_codec_before_model_dependencies(tmp_path,monkeypatch,group,device,codec):
    m=installer();calls=[]
    def run(args,**kw):
        calls.append(list(map(str,args)))
        if 'ls-remote' in args:return SimpleNamespace(stdout='a'*40+'\tHEAD')
        return SimpleNamespace(stdout='torch==2.11.0+rocm7.2\ntorchaudio==2.11.0+rocm7.2\ntorchvision==0.26.0+rocm7.2\n')
    monkeypatch.setattr(m,'run',run);monkeypatch.setattr(m,'verify',lambda *a:None)
    m.install_group('/python',tmp_path,device,group)
    codec_call=next(c for c in calls if 'torchcodec=='+codec in c)
    assert '--no-deps' in codec_call and 'https://download.pytorch.org/whl/cpu' in codec_call
    assert 'torchcodec=='+codec in (tmp_path/'torch-constraints.txt').read_text()


def test_audio_verify_rejects_torchaudio_encoder_failure(monkeypatch):
    m=installer();calls=[]
    def run(args,**kw):
        calls.append(args)
        if 'torchaudio.save' in str(args):raise RuntimeError('TorchCodec is required')
    monkeypatch.setattr(m,'run',run)
    with pytest.raises(RuntimeError,match='TorchCodec is required'):m.verify('/python','audio','rocm')
    assert any('AudioDecoder' in str(c) for c in calls)


def test_nested_codec_error_retains_safe_original_cause():
    error="ImportError: TorchCodec is required for save_with_torchcodec\nsubprocess.CalledProcessError: Command secret=PRIVATE failed"
    failure=_worker_failure(error,1)
    assert failure['category']=='worker_audio_codec_missing'
    assert failure['exception_types']==['ImportError','CalledProcessError']
    assert failure['metering_valid'] is False
    assert 'PRIVATE' not in json.dumps(failure)


def test_diagnostic_bundle_keeps_fixed_metadata_without_arbitrary_stderr(tmp_path,monkeypatch):
    from app import diagnostic_bundle as diag
    monkeypatch.setattr(diag,'enabled',lambda:True)
    monkeypatch.setattr(diag,'directory',lambda:tmp_path)
    record=logging.LogRecord('worker',logging.ERROR,__file__,1,'PRIVATE prompt token=SECRET',(),None)
    record.mta_worker_failure=_worker_failure("ModuleNotFoundError: No module named 'torchcodec'\nsecret=SECRET",1)
    diag.SafeEvents().emit(record)
    text=(tmp_path/'events.jsonl').read_text()
    failure=json.loads(text)['worker_failure']
    assert failure['missing_dependency']=='torchcodec'
    assert failure['exception_types']==['ModuleNotFoundError']
    assert failure['category']=='worker_audio_codec_missing'
    assert 'SECRET' not in text and 'PRIVATE' not in text and 'prompt' not in text


@pytest.mark.parametrize('extra',[{'category':[]},{'category':'private prompt'},{'exit_code':True}])
def test_invalid_failure_metadata_is_rejected(extra):
    d={'schema':'mta-worker-failure-v1','category':'worker_exit','exit_code':1,**extra}
    assert safe_failure_metadata(d) is None


def test_untrusted_details_are_not_persisted():
    d={'schema':'mta-worker-failure-v1','category':'worker_exit','exit_code':1,
       'missing_dependency':['SECRET'],'exception_types':['SECRET'],'stderr':'SECRET','metering_valid':True}
    assert safe_failure_metadata(d)=={'category':'worker_exit','exit_code':1,'metering_valid':False}
