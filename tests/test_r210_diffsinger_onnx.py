"""Interface/phoneme alignment safeguards; not substitute neural inference."""
import copy
import numpy as np
import pytest
from app.diffsinger_onnx import token_inputs,acoustic_inputs
from app.studio_asset_registry import validate_manifest


def manifest():
    names=['runtime/acoustic.onnx','runtime/dsconfig.yaml','runtime/vocoder.onnx','runtime/vocoder.yaml','phones.json','engine.txt','singer.txt','vocoder.txt']
    return {'schema':'mta-studio-bundle-1','id':'test-onnx','name':'Unit interface only','kind':'diffsinger','format':'openutau-onnx','languages':['en','vocalise'],
            'bindings':{'runtime_root':'runtime','acoustic':names[0],'config':names[1],'vocoder':names[2],'vocoder_config':names[3],'phonemes':names[4]},
            'files':{n:{'bytes':1,'sha256':'a'*64} for n in names},
            'policies':{'singer':'diffsinger-qixuan','vocoder':'diffsinger-vocoder'},
            'components':{'engine':'mta-analysis','acoustic':'diffsinger-qixuan','vocoder':'diffsinger-vocoder'},
            'component_files':{'engine':[names[5]],'acoustic':[names[0],names[1],names[4]],'vocoder':[names[2],names[3]]},
            'licenses':[{'policy_model':k,'notice':n,'evidence_url':'https://example.test/license'} for k,n in [('mta-analysis',names[5]),('diffsinger-qixuan',names[6]),('diffsinger-vocoder',names[7])]]}


def test_onnx_inventory_keeps_independent_component_policies_and_pins():
    value=manifest();assert validate_manifest(value)['format']=='openutau-onnx'
    for key in ('vocoder_config','acoustic'):
        broken=copy.deepcopy(value);del broken['bindings'][key]
        with pytest.raises(ValueError):validate_manifest(broken)
    broken=copy.deepcopy(value);broken['expression_defaults']={'voicing_db':float('nan')}
    with pytest.raises(ValueError):validate_manifest(broken)
    broken=copy.deepcopy(value);broken['format']='unreviewed-plugin'
    with pytest.raises(ValueError):validate_manifest(broken)


def test_language_embedding_is_used_only_for_cross_language_shared_tokens():
    mapping={'SP':1,'en/aa':2,'en/iy':3,'ja/i':3}
    tokens,lang=token_inputs(['SP','aa','en/iy'],mapping,{'en':1,'ja':2},'en')
    assert tokens.tolist()==[[1,2,3]] and lang.tolist()==[[0,0,1]]
    with pytest.raises(ValueError,match='missing'):token_inputs(['invented'],mapping,{'en':1},'en')


def test_frame_durations_share_one_cumulative_clock_and_f0_remains_score_control():
    ds={'ph_seq':'SP en/aa en/aa','ph_dur':'.1 .333 .333','f0_seq':'0 220 220','f0_timestep':.333}
    config={'sample_rate':44100,'hop_size':512,'use_breathiness_embed':True,'max_depth':.6}
    feed=acoustic_inputs(ds,config,{'SP':1,'en/aa':2},{'en':1},{'breathiness_db':-48.},4)
    frames=round(.766*44100/512+.5)
    assert int(feed['durations'].sum())==frames==feed['f0'].shape[1]
    assert feed['f0'][0,0]==0 and feed['f0'][0,-1]==220
    assert np.all(feed['breathiness']==-48.) and int(feed['steps'])==4
    with pytest.raises(ValueError,match='explicit'):acoustic_inputs(ds,config,{'SP':1,'en/aa':2},{'en':1},{})
    bad={**ds,'ph_dur':'.1 nan .3'}
    with pytest.raises(ValueError,match='duration'):acoustic_inputs(bad,config,{'SP':1,'en/aa':2},{'en':1},{})
