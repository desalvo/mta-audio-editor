"""Real parser/renderer orchestration, synthetic model sessions; no voicebank proof."""
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest
from app import diffsinger_onnx as backend, diffsinger_bridge as bridge


def digest(data):return hashlib.sha256(data).hexdigest()


@pytest.fixture
def singing(tmp_path,monkeypatch):
    from model_rights_fixtures import authorize_singing_fixture
    authorize_singing_fixture(monkeypatch,tmp_path)
    spectral={'sample_rate':44100,'hop_size':512,'win_size':2048,'fft_size':2048,'num_mel_bins':128,
              'mel_fmin':0,'mel_fmax':22050,'mel_base':'e','mel_scale':'slaney'}
    data={'config':json.dumps({**spectral,'acoustic':'acoustic','vocoder':'test-vocoder','phonemes':'phones','languages':'languages'}).encode(),
          'vocoder_config':json.dumps({**spectral,'name':'test-vocoder','model':'vocoder'}).encode(),
          'phones':b'{"SP": 1, "a": 2}','languages':b'{"en": 1}',
          'acoustic':b'fake acoustic','vocoder':b'fake vocoder'}
    for name,raw in data.items():(tmp_path/name).write_bytes(raw)
    value={'bindings':{k:k for k in ['config','vocoder_config','acoustic','vocoder']},
           'files':{k:{'bytes':len(v),'sha256':digest(v)} for k,v in data.items()},'languages':['en'],
           'licenses':[{'policy_model':model} for model in ('diffsinger-nishiren','diffsinger-vocoder')]}
    def asset(name):return tmp_path/name
    monkeypatch.setattr(backend,'inventory',lambda:(value,asset))
    for key in ['MTA_NEURAL_SINGER_CHECKPOINT','MTA_DIFFSINGER_VOCODER','MTA_NEURAL_SINGER_SHA256']:monkeypatch.delenv(key,raising=False)
    session=Mock(side_effect=[SimpleNamespace(get_inputs=lambda:[SimpleNamespace(name='f0')],
        run=lambda *_:[np.zeros((1,1,128),dtype=np.float32)]),
        SimpleNamespace(get_inputs=lambda:[SimpleNamespace(name=n) for n in ['mel','f0']],
        run=lambda *_:[np.full((1,512),.1,dtype=np.float32)])])
    monkeypatch.setattr(backend,'session',session)
    monkeypatch.setattr(backend,'acoustic_inputs',lambda *a,**kw:{'f0':np.ones((1,1),dtype=np.float32),'steps':4})
    monkeypatch.setattr(bridge,'select_score_phonemes',lambda value,**kw:value)
    monkeypatch.setattr(bridge,'ds_from_request',lambda _: {})
    request=tmp_path/'request.json';request.write_text(json.dumps({'schema':'mta-neural-singing-1','language':'en'}))
    return tmp_path,value,asset,request,session


def test_matching_configuration_reaches_both_pinned_sessions_and_real_wav(singing):
    import soundfile as sf
    root,value,asset,request,session=singing
    output=root/'voice.wav';backend.run(request,output)
    assert sf.info(output).samplerate==48000 and sf.info(output).frames>0
    assert session.call_count==2
    assert session.call_args_list[0].args==(root/'acoustic',value['files']['acoustic']['sha256'])
    assert session.call_args_list[1].args==(root/'vocoder',value['files']['vocoder']['sha256'])


@pytest.mark.parametrize('target',['config','vocoder_config','phones','languages'])
def test_configuration_changed_after_inventory_check_cannot_reach_model(singing,monkeypatch,target):
    root,value,asset,request,session=singing
    def changed(name):
        path=asset(name)
        if name==target:path.write_bytes(b'{"substituted":true}')
        return path
    monkeypatch.setattr(backend,'inventory',lambda:(value,changed))
    output=root/'voice.wav'
    with pytest.raises(ValueError,match='integrity'):backend.run(request,output)
    session.assert_not_called();assert not output.exists()


def test_inventory_parser_never_reads_substituted_bytes(tmp_path,monkeypatch):
    path=tmp_path/'manifest.json';original=b'{"schema":"synthetic"}'
    path.write_bytes(original)
    monkeypatch.setenv('MTA_DIFFSINGER_ONNX_INVENTORY',str(path))
    monkeypatch.setenv('MTA_DIFFSINGER_ONNX_INVENTORY_SHA256',digest(original))
    path.write_bytes(b'{"schema":"substituted"}')
    with pytest.raises(ValueError,match='integrity'):backend.inventory()


def test_lexicon_parser_rejects_swap_after_legacy_path_verification(tmp_path,monkeypatch):
    path=tmp_path/'lexicon.json';raw=b'{"schema":"mta-diffsinger-lexicon-1","language":"en","entries":{"a":"a"}}'
    path.write_bytes(raw)
    def replaced(*_):path.write_bytes(raw.replace(b'"a":"a"',b'"a":"x"'));return path
    monkeypatch.setattr(bridge,'safe_file',replaced)
    with pytest.raises(ValueError,match='integrity'):bridge.reviewed_lexicon(str(path),digest(raw))


def test_inventory_retains_uppercase_digest_compatibility(tmp_path,monkeypatch):
    from test_r210_diffsinger_onnx import manifest
    value=manifest()
    for name,entry in value['files'].items():
        path=tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'x')
        entry['sha256']=digest(b'x')
    path=tmp_path/'manifest.json';raw=json.dumps(value).encode();path.write_bytes(raw)
    monkeypatch.setenv('MTA_DIFFSINGER_ONNX_INVENTORY',str(path))
    monkeypatch.setenv('MTA_DIFFSINGER_ONNX_INVENTORY_SHA256',digest(raw).upper())
    loaded,_=backend.inventory()
    assert loaded==value
