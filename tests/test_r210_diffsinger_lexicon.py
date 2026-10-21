import hashlib
import json
import pytest
from app.diffsinger_bridge import reviewed_lexicon, phonemize_request, ds_from_request, select_score_phonemes


def make_lexicon(tmp_path, language='it', entries=None):
    path=tmp_path/'singer.json'
    path.write_text(json.dumps({'schema':'mta-diffsinger-lexicon-1','language':language,
                                'entries':entries or {'cia':'tS', 'o':'O'}}),encoding='utf-8')
    return path,hashlib.sha256(path.read_bytes()).hexdigest()


def test_italian_lexicon_to_ds(tmp_path):
    path,digest=make_lexicon(tmp_path)
    language,lexicon=reviewed_lexicon(path,digest)
    assert language=='it'
    score={'language':'it','notes':[{'start_ms':0,'duration_ms':500,'pitch':60,'syllable':'Cia'},
                                    {'start_ms':500,'duration_ms':500,'pitch':62,'syllable':'O'}]}
    ds=ds_from_request(phonemize_request(score,lexicon))
    assert ds['ph_seq']=='tS O'
    assert score['notes'][0]['syllable']=='Cia'


def test_french_reviewed_lexicon(tmp_path):
    path,digest=make_lexicon(tmp_path,'fr',{'bon':'bO'})
    language,lexicon=reviewed_lexicon(path,digest)
    assert language=='fr'
    assert phonemize_request({'notes':[{'syllable':'BON'}]},lexicon)['notes'][0]['syllable']=='bO'


def test_absent_syllable_fails_closed(tmp_path):
    path,digest=make_lexicon(tmp_path)
    _,lexicon=reviewed_lexicon(path,digest)
    with pytest.raises(ValueError,match='absent'):
        phonemize_request({'notes':[{'syllable':'missing'}]},lexicon)


def test_tampered_lexicon_rejected(tmp_path):
    path,digest=make_lexicon(tmp_path)
    path.write_text(path.read_text()+' ')
    with pytest.raises(ValueError,match='checksum'):
        reviewed_lexicon(path,digest)


def test_invalid_bank_token_rejected(tmp_path):
    path,digest=make_lexicon(tmp_path,entries={'cia':'a b'})
    with pytest.raises(ValueError,match='phoneme'):
        reviewed_lexicon(path,digest)


def test_english_reviewed_lexicon_end_to_end_score(tmp_path):
    path, digest = make_lexicon(tmp_path, 'en', {'hel': 'h', 'lo': 'lO'})
    score = {'language': 'en', 'use_reviewed_lexicon': True, 'notes': [
        {'start_ms': 0, 'duration_ms': 400, 'pitch': 60, 'syllable': 'HEL'},
        {'start_ms': 400, 'duration_ms': 400, 'pitch': 62, 'syllable': 'lo'},
    ]}
    normalized = select_score_phonemes(score, lexicon_path=str(path), lexicon_sha256=digest)
    assert ds_from_request(normalized)['ph_seq'] == 'h lO'
    assert score['notes'][0]['syllable'] == 'HEL'

def test_english_direct_bank_phonemes_remain_compatible():
    score = {'language': 'en', 'notes': [{'start_ms': 0, 'duration_ms': 500,
                                         'pitch': 60, 'syllable': 'AH'}]}
    assert ds_from_request(select_score_phonemes(score))['ph_seq'] == 'AH'

def test_english_reviewed_lexicon_language_mismatch_fails(tmp_path):
    path, digest = make_lexicon(tmp_path, 'fr', {'hel': 'h'})
    with pytest.raises(ValueError, match='language does not match'):
        select_score_phonemes({'language': 'en', 'use_reviewed_lexicon': True,
                               'notes': [{'syllable': 'hel'}]},
                              lexicon_path=str(path), lexicon_sha256=digest)

def test_english_missing_syllable_fails_closed(tmp_path):
    path, digest = make_lexicon(tmp_path, 'en', {'hello': 'h'})
    with pytest.raises(ValueError, match='absent'):
        select_score_phonemes({'language': 'en', 'use_reviewed_lexicon': True,
                               'notes': [{'syllable': 'world'}]},
                              lexicon_path=str(path), lexicon_sha256=digest)

def test_diffsinger_rejects_non_boolean_lexicon_enable():
    with pytest.raises(ValueError, match='selection'):
        select_score_phonemes({'language': 'en', 'use_reviewed_lexicon': 'false'})
