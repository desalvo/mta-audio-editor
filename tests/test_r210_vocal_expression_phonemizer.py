"""Real optional G2P plus score/DSP tests; no simulated neural quality claim."""
import hashlib
import json
import math
import pytest
from app.vocal_expression import Expression, f0_curve, apply_dynamics
from app.vocal_phonemizer import load_profile, map_ipa, phonemize_score, ipa_for_text
from app.diffsinger_bridge import ds_from_request
from app.vocal_synthesis import Settings, validate_voice_lyrics
from app.music_interchange import MusicPart
from app.models import MidiNote


def note(**values):
    return {'pitch':69,'start_ms':0,'duration_ms':1000,'syllable':'a','velocity':127,**values}


def test_f0_absolute_pitch_rests_and_timing():
    curve=f0_curve([note(start_ms=200,duration_ms=400)],{})
    assert all(v==0 for v in curve[:40])
    assert all(abs(v-440)<1e-8 for v in curve[40:120])
    assert curve[120]==0


def test_vibrato_delay_frequency_depth_and_gate():
    cfg={'vibrato_cents':100.,'vibrato_hz':5.,'vibrato_delay_ms':200.,'gate':.8}
    curve=f0_curve([note()],cfg)
    assert curve[20]==440
    assert 440*2**(-1/12)-1e-6<=min(curve[60:150])
    assert max(curve[60:150])<=440*2**(1/12)+1e-6
    assert len(set(round(v,3) for v in curve[60:150]))>10
    assert all(v==0 for v in curve[160:])


def test_presets_allow_explicit_overrides():
    assert Expression(preset='gentle').resolved().dynamics==.75
    assert Expression(preset='gentle',dynamics=.5).resolved().dynamics==.5
    assert Expression(preset='sustained').resolved().vibrato_cents==35
    original=Expression(preset='gentle')
    reloaded=Expression.model_validate(original.model_dump())
    assert reloaded.resolved()==original.resolved()


@pytest.mark.parametrize('settings',[{'vibrato_hz':float('nan')},{'gate':0},{'dynamics':1.1},{'energy_db':1}])
def test_expression_refuses_invalid_values(settings):
    with pytest.raises(ValueError):Expression(**settings)


def test_neural_dynamics_are_real_sample_envelope():
    import numpy as np
    audio=np.ones(1200,dtype='float32')
    out=apply_dynamics(audio,1000,[note(start_ms=100,duration_ms=500)],{'dynamics':.5,'attack_ms':20.,'release_ms':20.},.8)
    assert out[:100].sum()==0 and out[600:].sum()==0
    assert out[0]==0 and out[200]==pytest.approx(.4)
    assert out[100]<out[110]<out[200] and out[599]==0


def profile(language='it'):
    return {'schema':'mta-bank-phonemes-1','language':language,'bank_sha256':'a'*64,
        'inventory':['SP','a','b','tS','O','l'],'vowels':['a','O'],
        'ipa_map':{'a':['a'],'b':['b'],'tʃ':['tS'],'ɔ̃':['O'],'l':['l'],'ɑː':['a'],'æ':['a']}}


def test_reviewed_profile_is_pinned_and_inventory_checked(tmp_path,monkeypatch):
    monkeypatch.delenv('MTA_NEURAL_SINGER_SHA256',raising=False)
    p=tmp_path/'profile.json';p.write_text(json.dumps(profile()))
    digest=hashlib.sha256(p.read_bytes()).hexdigest()
    assert load_profile(str(p),digest)['language']=='it'
    monkeypatch.setenv('MTA_NEURAL_SINGER_SHA256','b'*64)
    with pytest.raises(ValueError,match='different voicebank'):load_profile(str(p),digest)
    monkeypatch.delenv('MTA_NEURAL_SINGER_SHA256')
    p.write_text(p.read_text()+' ')
    with pytest.raises(ValueError,match='checksum'):load_profile(str(p),digest)


def test_map_preserves_ipa_units_not_guessed_phones():
    assert map_ipa('bˈɔ̃',profile('fr'))==['b','O']
    assert map_ipa('tʃˈa',profile())==['tS','a']
    with pytest.raises(ValueError,match='absent'):map_ipa('z',profile())


@pytest.mark.parametrize('language,text,ipa,expected',[('it','cia','tʃˈa',['tS','a']),('fr','bon','bˈɔ̃',['b','O']),('en','la','lˈɑː',['l','a'])])
def test_ipa_bank_mapping_and_multiphone_duration(monkeypatch,language,text,ipa,expected):
    monkeypatch.setattr('app.vocal_phonemizer.ipa_for_text',lambda t,l:ipa)
    score=phonemize_score({'language':language,'notes':[note(syllable=text)]},profile(language))
    assert score['notes'][0]['phonemes']==expected
    ds=ds_from_request(score)
    assert ds['ph_seq']==' '.join(expected)
    assert sum(map(float,ds['ph_dur'].split()))==pytest.approx(1.,abs=1e-6)
    assert ds['ph_num']=='2' and len(ds['f0_seq'].split())==201


@pytest.mark.parametrize('language,text',[('it','la'),('en','la'),('fr','bon')])
def test_real_espeak_g2p_languages(language,text):
    pytest.importorskip('espeakng_loader')
    ipa=ipa_for_text(text,language)
    assert ipa.strip() and any(c.isalpha() for c in ipa)
    score=phonemize_score({'language':language,'notes':[note(syllable=text)]},profile(language))
    assert len(ds_from_request(score)['f0_seq'].split())==201


def test_g2p_rejects_markup():
    with pytest.raises(ValueError):ipa_for_text('[[evil]]','en')


def test_it_fr_settings_and_note_alignment():
    part=MusicPart(id='singer',name='Singer',notes=[MidiNote(id='n',pitch=60,start_ms=0,duration_ms=500)])
    for language in ('it','fr','en'):
        cfg=Settings(backend='diffsinger',language=language,syllables=['la'],pronunciation='espeak')
        validate_voice_lyrics([part],cfg)
        with pytest.raises(ValueError):validate_voice_lyrics([part],cfg.model_copy(update={'syllables':[]}))
    with pytest.raises(ValueError,match='OddVoices'):Settings(language='it')


def test_ds_optional_embedding_curves_and_native_legacy():
    ds=ds_from_request({'notes':[note()], 'expression':{'energy_db':-30.,'gender':.2,'speed':1.1}})
    assert ds['ph_seq']=='a' and ds['gender']==.2
    assert len(ds['energy'].split())==len(ds['f0_seq'].split())
    assert ds['energy_timestep']==ds['f0_timestep']
    assert all(math.isfinite(float(v)) for v in ds['f0_seq'].split())


def test_vocoder_has_independent_policy_and_free_only_is_stricter(monkeypatch):
    from app import model_license_policy as policy
    def decision(model):
        return policy.Decision(model,'free_only' if model=='diffsinger-vocoder' else 'cost_recovery','https://example.com','a'*64)
    monkeypatch.setattr(policy,'evaluate_model',decision)
    monkeypatch.setenv('MTA_NEURAL_SINGER_POLICY_MODEL','singer')
    outcome=policy.evaluate('vocal-synthesis',{'settings':{'backend':'diffsinger'}})
    assert outcome.model_id=='singer' and not outcome.billable
    def denied(model):
        if model=='diffsinger-vocoder':raise policy.LicenseDenied('Vocoder not authorized')
        return decision(model)
    monkeypatch.setattr(policy,'evaluate_model',denied)
    with pytest.raises(policy.LicenseDenied,match='Vocoder'):policy.evaluate('vocal-synthesis',{'settings':{'backend':'diffsinger'}})


def test_full_diffsinger_bridge_uses_exact_config_checkpoint_and_score(tmp_path,monkeypatch):
    from model_rights_fixtures import authorize_singing_fixture
    authorize_singing_fixture(monkeypatch,tmp_path)
    """Contract test with test PCM, explicitly not neural model inference."""
    import soundfile as sf
    import numpy as np
    import yaml
    from app.diffsinger_bridge import run
    root=tmp_path/'runtime';experiment=root/'checkpoints'/'singer';experiment.mkdir(parents=True)
    (root/'scripts').mkdir();(root/'scripts'/'infer.py').write_text('# contract fixture')
    interpreter=tmp_path/'python';interpreter.write_bytes(b'fixture')
    checkpoint=experiment/'model_ckpt_steps_123.ckpt';checkpoint.write_bytes(b'fixture weights')
    vocoder=root/'vocoder.pt';vocoder.write_bytes(b'fixture vocoder')
    config=experiment/'config.yaml';config.write_text(yaml.safe_dump({'vocoder_ckpt':'vocoder.pt','use_energy_embed':True}))
    digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    for key,value in {'MTA_DIFFSINGER_ROOT':str(root),'MTA_DIFFSINGER_EXPERIMENT':'singer',
            'MTA_DIFFSINGER_PYTHON':str(interpreter),'MTA_DIFFSINGER_PYTHON_SHA256':digest(interpreter),
            'MTA_NEURAL_SINGER_CHECKPOINT':str(checkpoint),'MTA_NEURAL_SINGER_SHA256':digest(checkpoint),
            'MTA_DIFFSINGER_VOCODER':str(vocoder),'MTA_DIFFSINGER_VOCODER_SHA256':digest(vocoder),
            'MTA_DIFFSINGER_CONFIG_SHA256':digest(config)}.items():monkeypatch.setenv(key,value)
    seen=[]
    def inference(argv,**kwargs):
        from pathlib import Path
        assert argv[argv.index('--ckpt')+1]=='123'
        assert argv[1].endswith('studio_offline_runner.py') and argv[2].endswith('scripts/infer.py')
        ds=json.loads(Path(argv[argv.index('acoustic')+1]).read_text())
        assert ds['f0_timestep']==.005 and ds['energy_timestep']==.005
        assert len(ds['f0_seq'].split())==201 and ds['ph_seq']=='a'
        target=Path(argv[argv.index('--out')+1])/'singer.wav'
        sf.write(target,np.sin(np.arange(22050)*2*np.pi*440/22050).astype('float32')*.2,22050)
        seen.append(argv)
    monkeypatch.setattr('app.diffsinger_bridge.subprocess.run',inference)
    request=tmp_path/'request.json';request.write_text(json.dumps({'schema':'mta-neural-singing-1',
        'language':'en','notes':[note()], 'expression':{'energy_db':-30.}}))
    output=tmp_path/'output.wav';run(request,output)
    assert seen and sf.info(output).samplerate==48000 and sf.info(output).duration==pytest.approx(1.)
    config.write_text(config.read_text()+'# tampered')
    with pytest.raises(ValueError,match='checksum'):run(request,output)
