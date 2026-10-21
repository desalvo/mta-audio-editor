"""G2P runtime and contextual alignment contracts; real inference is separate."""
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from app.vocal_phonemizer import phonemize_configured_score, phonemize_score, load_profile, map_ipa
from app.qixuan_profiles import build_profiles
from test_r210_qixuan_itfr_profiles import INVENTORY


def score(language='fr', text='les amis'):
    return {'language': language, 'lyric_text': text, 'notes': [
        {'id': str(i), 'pitch': 60+i, 'start_ms': i*500, 'duration_ms': 500, 'velocity': 96, 'syllable': 'la'}
        for i in range(3)]}


def setup_runtime(tmp_path, language='fr'):
    p=build_profiles(INVENTORY, 'a'*64)[language]
    profile=tmp_path/'profile.json';profile.write_text(json.dumps(p))
    python=tmp_path/'python';python.write_bytes(b'operator interpreter')
    env={'MTA_DIFFSINGER_PYTHON':str(python),'MTA_DIFFSINGER_PYTHON_SHA256':hashlib.sha256(python.read_bytes()).hexdigest(),
         'MTA_DIFFSINGER_PHONEMES':str(profile),'MTA_DIFFSINGER_PHONEMES_SHA256':hashlib.sha256(profile.read_bytes()).hexdigest(),
         'MTA_NEURAL_SINGER_SHA256':'a'*64}
    return p,env


def test_context_preserves_real_french_liaison_and_word_regions(monkeypatch):
    observed=[]
    def ipa(text, language):
        observed.append((text,language));return 'le-z amˈi'
    monkeypatch.setattr('app.vocal_phonemizer.ipa_for_text',ipa)
    result=phonemize_score(score(),build_profiles(INVENTORY,'a'*64)['fr'])
    assert observed==[('les amis','fr')]
    assert result['notes'][0]['phonemes']==['en/l','ja/e','en/z']
    assert [n['word_index'] for n in result['notes']]==[0,1,1]
    assert result['pronunciation_profile']['contextual_g2p'] is True


def test_context_word_mismatch_is_not_guessed(monkeypatch):
    monkeypatch.setattr('app.vocal_phonemizer.ipa_for_text',lambda *args:'le am i')
    with pytest.raises(ValueError,match='word boundaries differ'):
        phonemize_score(score(),build_profiles(INVENTORY,'a'*64)['fr'])


def test_liaison_marker_removal_is_pinned_not_unknown_fallback():
    p=build_profiles(INVENTORY,'a'*64)['fr']
    assert map_ipa('le-z',p)==['en/l','ja/e','en/z']
    assert map_ipa('le-',p)==['en/l','ja/e']
    with pytest.raises(ValueError,match='absent'):map_ipa('le#',p)


def test_context_selection_is_validated(tmp_path):
    p,env=setup_runtime(tmp_path);p['contextual_g2p']='yes'
    path=Path(env['MTA_DIFFSINGER_PHONEMES']);path.write_text(json.dumps(p))
    with pytest.raises(ValueError,match='contextual'):
        load_profile(str(path),hashlib.sha256(path.read_bytes()).hexdigest(),'a'*64)


def test_external_g2p_uses_pinned_interpreter_offline_helper(tmp_path,monkeypatch):
    p,env=setup_runtime(tmp_path);request=score();response=copy.deepcopy(request)
    for n in response['notes']:n['phonemes']=['ja/a']
    observed=[]
    monkeypatch.setattr('importlib.util.find_spec',lambda name:None)
    def run(argv,**kwargs):
        observed.append((argv,kwargs));return SimpleNamespace(stdout=json.dumps(response).encode())
    monkeypatch.setattr('subprocess.run',run)
    result=phonemize_configured_score(request,p,env)
    argv,kwargs=observed[0]
    assert argv[:2]==[env['MTA_DIFFSINGER_PYTHON'],'-I']
    assert argv[2].endswith('vocal_g2p_bridge.py')
    assert kwargs['env']['HF_HUB_OFFLINE']=='1' and kwargs['env']['TRANSFORMERS_OFFLINE']=='1'
    assert json.loads(kwargs['input'])==request
    assert result['pronunciation_profile']['mode']=='cross-language'


def test_modified_external_interpreter_is_rejected_before_start(tmp_path,monkeypatch):
    p,env=setup_runtime(tmp_path);Path(env['MTA_DIFFSINGER_PYTHON']).write_bytes(b'modified')
    monkeypatch.setattr('importlib.util.find_spec',lambda name:None)
    with pytest.raises(ValueError,match='checksum'):phonemize_configured_score(score(),p,env)


def test_external_g2p_cannot_move_or_relabel_music(tmp_path,monkeypatch):
    p,env=setup_runtime(tmp_path);result=score()
    for n in result['notes']:n['phonemes']=['ja/a']
    result['notes'][0]['start_ms']=40
    monkeypatch.setattr('importlib.util.find_spec',lambda name:None)
    monkeypatch.setattr('subprocess.run',lambda *a,**k:SimpleNamespace(stdout=json.dumps(result).encode()))
    with pytest.raises(ValueError,match='musical data'):phonemize_configured_score(score(),p,env)


def test_broken_local_library_is_not_silently_replaced(tmp_path,monkeypatch):
    p,env=setup_runtime(tmp_path);env['MTA_ESPEAK_LIBRARY']='/missing/explicit/library'
    def broken(*args):raise RuntimeError('explicit local library failure')
    monkeypatch.setattr('app.vocal_phonemizer.phonemize_score',broken)
    with pytest.raises(RuntimeError,match='explicit local'):phonemize_configured_score(score(),p,env)
