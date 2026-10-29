"""Stem dialogs use readable controls and the configured inference interpreter."""
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest
from app import main, ai_models

ROOT = Path(__file__).parents[1]


def test_catalog_probes_configured_backing_runtime(monkeypatch):
    monkeypatch.setattr(main, 'NATIVE_SINGLE_USER', False)
    monkeypatch.setattr(ai_models, '_isolated_model_python', lambda kind: '/trusted/audio/bin/python')
    calls=[]
    def run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout='True\n')
    monkeypatch.setattr(main.subprocess, 'run', run)
    assert main._lead_backing_engine_available()
    assert calls[0][0][0]=='/trusted/audio/bin/python'
    assert calls[0][1]['timeout']==10


@pytest.mark.parametrize('failure', ['absent', 'broken', 'timeout'])
def test_catalog_does_not_claim_broken_worker_is_available(monkeypatch, failure):
    monkeypatch.setattr(main, 'NATIVE_SINGLE_USER', False)
    monkeypatch.setattr(ai_models, '_isolated_model_python', lambda kind: '/trusted/python')
    def run(args, **kwargs):
        if failure=='timeout':raise subprocess.TimeoutExpired(args,10)
        return SimpleNamespace(returncode=0 if failure=='absent' else 1, stdout='False\n')
    monkeypatch.setattr(main.subprocess,'run',run)
    assert not main._lead_backing_engine_available()


def test_model_download_uses_worker_and_shared_cache(monkeypatch,tmp_path):
    monkeypatch.setattr(main, 'NATIVE_SINGLE_USER', False)
    monkeypatch.setattr(main, 'LEAD_BACKING_MODEL_DIR', tmp_path)
    monkeypatch.setattr(ai_models, '_isolated_model_python', lambda kind: '/trusted/python')
    calls=[]
    def download(python,kind,model_id,model_dir=None):
        calls.append((python,kind,model_id,model_dir))
        (model_dir/'UVR_MDXNET_KARA_2.onnx').write_bytes(b'model')
        return {'id':model_id,'installed':True}
    monkeypatch.setattr(ai_models,'_isolated_model_download',download)
    # Mock a separately authorized weight solely for the transport fixture.
    from app import model_license_policy
    monkeypatch.setattr(model_license_policy,'evaluate_model',lambda model_id: True)
    result=main._download_lead_backing_model('uvr_mdxnet_kara_2')
    assert result['installed']
    assert calls==[('/trusted/python','backing-vocals','uvr_mdxnet_kara_2',tmp_path)]
    with pytest.raises(ValueError):main._download_lead_backing_model('../unsafe')
    assert len(calls)==1


def test_native_download_does_not_launch_server_worker(monkeypatch,tmp_path):
    monkeypatch.setattr(main, 'NATIVE_SINGLE_USER', True)
    monkeypatch.setattr(main, 'LEAD_BACKING_MODEL_DIR', tmp_path)
    monkeypatch.setattr(ai_models, '_isolated_model_python', lambda kind: pytest.fail('native routed to server runtime'))
    # A missing optional local package still reports unavailability normally.
    main._lead_backing_engine_available()


def test_server_split_stays_in_global_queue(monkeypatch,tmp_path,reviewed_backing_policy):
    monkeypatch.setattr(main,'_ai_external_engine',lambda kind: kind=='backing-vocals')
    calls=[]
    def infer(kind,source,options):
        calls.append((kind,options))
        return {'audio':{'lead.wav':b'lead','backing.wav':b'backing'}},'server-job'
    monkeypatch.setattr(main,'_native_remote_infer',infer)
    lead,backing,method=main._split_lead_backing_vocals(tmp_path/'source.wav',tmp_path/'out',model_id='uvr_mdxnet_kara_2')
    assert lead.read_bytes()==b'lead' and backing.read_bytes()==b'backing'
    assert method=='remote:server-job'
    assert calls==[('backing-vocals',{'model':'uvr_mdxnet_kara_2'})]


def test_stem_buttons_have_explicit_readable_colors():
    css=(ROOT/'app/static/app.css').read_text(encoding='utf-8')
    rule=css.split('.stem-workflow .utility-btn{')[-1].split('}')[0]
    assert 'background:#183247!important' in rule
    assert 'color:#f4fbff!important' in rule
    assert '-webkit-text-fill-color:#f4fbff!important' in rule
    assert '.stem-workflow .utility-btn:focus-visible' in css


def test_real_bridge_downloads_without_importing_separator_in_web_runtime(tmp_path,monkeypatch):
    import os
    import sys
    package=tmp_path/'fake/audio_separator';package.mkdir(parents=True)
    (package/'__init__.py').write_text('')
    (package/'separator.py').write_text('from pathlib import Path\nclass Separator:\n def __init__(self,model_file_dir,**kw):self.folder=Path(model_file_dir)\n def download_model_files(self,name):(self.folder/name).write_bytes(b"model")\n')
    env=dict(os.environ,PYTHONPATH=str(tmp_path/'fake'))
    folder=tmp_path/'models'
    command=[sys.executable,str(ROOT/'app/ai_model_download.py'),'--kind','backing-vocals','--model','uvr_mdxnet_kara_2','--model-dir',str(folder)]
    result=subprocess.run(command,env=env,capture_output=True,text=True,timeout=30)
    assert result.returncode != 0 and 'SHA-256' in result.stderr
    assert (folder/'UVR_MDXNET_KARA_2.onnx').read_bytes()==b'model'
    command[command.index('uvr_mdxnet_kara_2')]='../../unsafe'
    result=subprocess.run(command,env=env,capture_output=True,text=True,timeout=30)
    assert result.returncode!=0 and 'Unsupported lead/backing model' in result.stderr
