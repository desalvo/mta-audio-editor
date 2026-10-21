"""Explicit IPA corpus/profile tests, not substituted neural/G2P inference."""
import hashlib
import json
import pytest
from app.qixuan_profiles import build_profiles
from app.vocal_phonemizer import load_profile,map_ipa,phonemize_score,profile_metadata
from app.diffsinger_bridge import ds_from_request

EN='aa ae ah ao aw ax ay b ch d dh dx eh er ey f g hh ih iy jh k l m n ng ow oy p r s sh t th uh uw v w y z zh'.split()
INVENTORY=['SP',*['en/'+p for p in EN],'ja/a','ja/e','ja/o','ja/r','ja/ny','ja/ts','zh/u','zh/v','zh/ve','zh/ang','zh/ong','zh/eng']


def profiles():return build_profiles(INVENTORY,'a'*64)


def test_profiles_explicitly_disclose_cross_language_projection():
    values=profiles();assert set(values)=={'it','en','fr'}
    assert values['en']['pronunciation_mode']=='native-inventory'
    for lang in ('it','fr'):
        p=values[lang]
        assert p['pronunciation_mode']=='cross-language'
        assert p['acoustic_languages']==['en','ja','zh']
        assert p['approximations'] and 'not native IT/FR' in p['notes']
        assert all(phone in INVENTORY for phones in p['ipa_map'].values() for phone in phones)
        assert not any(phone.startswith(('it/','fr/')) for phones in p['ipa_map'].values() for phone in phones)


@pytest.mark.parametrize('language,ipa,phones',[
 ('it','tʃˈa',['en/ch','ja/a']),('it','ɲˈɔkːi',['ja/ny','en/ao','en/k','en/k','en/iy']),
 ('it','ʎˈi',['en/l','en/y','en/iy']),('it','rˈoːso',['ja/r','ja/o','en/s','ja/o']),
 ('fr','bɔ̃ʒˈuʁ',['en/b','zh/ong','en/zh','zh/u','en/r']),('fr','kˈœʁ',['en/k','zh/ve','en/r']),
 ('fr','lˈyn',['en/l','zh/v','en/n']),('fr','pˈɛ̃',['en/p','zh/eng']),('fr','blˈɑ̃',['en/b','en/l','zh/ang'])])
def test_explicit_ipa_corpus(language,ipa,phones):
    assert map_ipa(ipa,profiles()[language])==phones


def test_normalized_nasal_diacritics():
    fr=profiles()['fr']
    assert map_ipa('bˈa\u0303',fr)==map_ipa('bˈã',fr)==['en/b','zh/ang']
    assert map_ipa('kˈœ\u0303',fr)==['en/k','zh/eng']


def test_unknown_phone_does_not_silently_fallback():
    with pytest.raises(ValueError,match='absent'):map_ipa('q',profiles()['fr'])
    with pytest.raises(ValueError,match='missing'):build_profiles(['SP','en/a'],'a'*64)


def test_profile_pinning_and_disclosures(tmp_path,monkeypatch):
    monkeypatch.delenv('MTA_NEURAL_SINGER_SHA256',raising=False)
    p=profiles()['fr'];path=tmp_path/'fr.json';path.write_text(json.dumps(p));sha=hashlib.sha256(path.read_bytes()).hexdigest()
    assert profile_metadata(load_profile(str(path),sha,'a'*64))['mode']=='cross-language'
    with pytest.raises(ValueError,match='different voicebank'):load_profile(str(path),sha,'b'*64)
    p['approximations']={};path.write_text(json.dumps(p));sha=hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError,match='disclosure'):load_profile(str(path),sha,'a'*64)


def test_text_and_syllables_keep_projection_metadata(monkeypatch):
    monkeypatch.setattr('app.vocal_phonemizer.ipa_for_text',lambda text,lang:'lˈyn')
    request={'language':'fr','notes':[{'id':'n','pitch':60,'start_ms':0,'duration_ms':1000,'velocity':96,'syllable':'lune'}]}
    for r in (request,{**request,'lyric_text':'lune'}):
        result=phonemize_score(r,profiles()['fr'])
        assert result['pronunciation_profile']['mode']=='cross-language'
        assert result['notes'][0]['phonemes']==['en/l','zh/v','en/n']
        ds=ds_from_request(result)
        assert sum(map(float,ds['ph_dur'].split()))==pytest.approx(1.,abs=1e-6)
        assert ds['lang']=='en'


def test_legacy_profile_metadata_stays_absent():
    assert profile_metadata({'language':'it'})=={}


def test_upgrade_rejects_unpinned_source(tmp_path):
    from scripts.build_qixuan_onnx_bundle import upgrade
    source=tmp_path/'unknown.zip';source.write_bytes(b'not the complete original');dest=tmp_path/'out.zip'
    with pytest.raises(ValueError,match='SHA-256'):upgrade(source,dest)
    assert not dest.exists()


def test_projection_is_visible_before_generation():
    from pathlib import Path
    source=(Path(__file__).resolve().parents[1]/'app/static/studio_extended.js').read_text()
    assert 'studioPronunciationProfileNotice' in source and 'pronunciation_modes' in source
    assert 'notice.textContent=' in source


@pytest.mark.parametrize('word,ipa,nuclei',[('ciao','tʃˈao',1),('cuore','kʊˈɔre',2),('paura','paˈʊra',3),('gioia','dʒˈɔia',2),('mio','mˈio',2),('buongiorno','bʊondʒˈɔrno',3),('aiuto','aˈiuto',3)])
def test_italian_glide_and_hiatus_alignment(word,ipa,nuclei):
    p=profiles()['it'];phones=map_ipa(ipa,p)
    assert sum(phone in p['vowels'] for phone in phones)==nuclei


def test_literal_rewrites_have_bounded_expansion():
    p=profiles()['it'];p['ipa_rewrites']={'a':'a'*40,'aa':'a'*40,'aaa':'a'*40}
    with pytest.raises(ValueError,match='budget'):map_ipa('a'*4000,p)


def test_explicit_real_bank_phone_prefixes_are_editable_but_not_commands():
    from app.vocal_synthesis import Settings
    value=Settings(backend='diffsinger',language='it',explicit_phones=[['en/ch','ja/a']])
    assert value.explicit_phones==[['en/ch','ja/a']]
    for phone in ['en/a b','en/a\n','en/\x00a']:
        with pytest.raises(ValueError):Settings(backend='diffsinger',explicit_phones=[[phone]])


def test_default_vocalise_uses_pinned_vowel_map(tmp_path):
    from app.diffsinger_bridge import select_score_phonemes
    p=profiles()['en'];path=tmp_path/'en.json';path.write_text(json.dumps(p))
    env={'MTA_DIFFSINGER_PHONEMES':str(path),'MTA_DIFFSINGER_PHONEMES_SHA256':hashlib.sha256(path.read_bytes()).hexdigest(),
         'MTA_NEURAL_SINGER_SHA256':'a'*64}
    request={'language':'vocalise','pronunciation':'native','notes':[{'syllable':'A'}]}
    result=select_score_phonemes(request,environ=env)
    assert result['notes'][0]['phonemes']==['en/aa']
    assert result['pronunciation_profile']['lyric_language']=='vocalise'
    with pytest.raises(ValueError,match='Vocalise symbol'):
        select_score_phonemes({**request,'notes':[{'syllable':'UNKNOWN'}]},environ=env)
