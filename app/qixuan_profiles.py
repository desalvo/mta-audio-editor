"""Pinned Qixuan 2.7 phone profiles: EN and explicit IT/FR projections.

The original acoustic bank has English/Japanese/Mandarin phones, not Italian or
French training. Projection is a declared approximation; it never renames IDs
or manufactures an unsupported acoustic language or model-quality certificate.
"""
import unicodedata
from .vocal_phonemizer import validate_phones

MODE_NOTE=('Italian/French lyrics use existing English, Japanese and Mandarin bank phones. '
           'Rhotics, palatals, rounded mid/front and nasal vowels are approximated. '
           'This is cross-language synthesis, not native IT/FR pronunciation certification.')


def _profile(language, inventory, acoustic_sha, mapping, vowels, approximations=None, ipa_rewrites=None):
    if language not in ('en','it','fr'):
        raise ValueError('Unsupported Qixuan lyric profile language')
    mapping={unicodedata.normalize('NFC',ipa):phones for ipa,phones in mapping.items()}
    for phones in mapping.values():validate_phones(phones,inventory)
    for phone in vowels:validate_phones([phone],inventory)
    return {'schema':'mta-bank-phonemes-1','language':language,'bank_language':'en',
            'bank_sha256':acoustic_sha,'inventory':list(inventory),'ipa_map':mapping,'vowels':vowels,
            'pronunciation_mode':'native-inventory' if language=='en' else 'cross-language',
            'acoustic_languages':['en','ja','zh'],
            'approximations':approximations or {},'ipa_rewrites':ipa_rewrites or {},
            'notes':('English phoneme mapping; score durations and F0. Musical pronunciation review required.'
                     if language=='en' else MODE_NOTE)}


def build_profiles(inventory, acoustic_sha):
    en={
        'ɑ':'aa','a':'aa','æ':'ae','ɐ':'ah','ʌ':'ah','ə':'ax','ɔ':'ao','ɒ':'ao',
        'ɛ':'eh','e':'eh','ɜ':'er','ɚ':'er','ɝ':'er','i':'iy','ɪ':'ih','u':'uw','ʊ':'uh',
        'oʊ':'ow','əʊ':'ow','eɪ':'ey','aɪ':'ay','aʊ':'aw','ɔɪ':'oy',
        'b':'b','d':'d','f':'f','g':'g','ɡ':'g','h':'hh','k':'k','l':'l','ɫ':'l',
        'm':'m','n':'n','ŋ':'ng','p':'p','ɹ':'r','r':'r','s':'s','ʃ':'sh',
        't':'t','θ':'th','ð':'dh','v':'v','w':'w','j':'y','z':'z','ʒ':'zh',
        'tʃ':'ch','dʒ':'jh','ɾ':'dx'}
    en.update({ipa+'ː':phone for ipa,phone in list(en.items())
               if phone in ('aa','ae','ah','ao','ax','eh','er','ih','iy','uh','uw')})
    en_mapping={ipa:['en/'+phone] for ipa,phone in en.items()}
    shared={ipa:['en/'+phone] for ipa,phone in {
        'b':'b','d':'d','f':'f','ɡ':'g','g':'g','k':'k','l':'l','m':'m','n':'n',
        'ŋ':'ng','p':'p','s':'s','ʃ':'sh','t':'t','v':'v','w':'w','j':'y','z':'z',
        'ʒ':'zh','tʃ':'ch','dʒ':'jh','h':'hh'}.items()}
    vowels={'a':['ja/a'],'ɑ':['en/aa'],'e':['ja/e'],'ɛ':['en/eh'],'i':['en/iy'],
            'o':['ja/o'],'ɔ':['en/ao'],'u':['zh/u'],'ə':['en/ax'],
            'ɪ':['en/ih'],'ʊ':['en/uh']}
    it={**shared,**vowels,'r':['ja/r'],'ɾ':['ja/r'],'ɲ':['ja/ny'],'ʎ':['en/l','en/y'],
        'ts':['ja/ts'],'dz':['en/d','en/z'],'ɱ':['en/m']}
    it_approximations={
        'r':'Japanese tap substitutes for Italian trill; no learned Italian trill is asserted.',
        'ɲ':'Japanese palatalized nasal approximates the Italian palatal nasal.',
        'ʎ':'English l+y sequence approximates the Italian palatal lateral.',
        'dz':'English d+z sequence approximates the voiced alveolar affricate.',
        'ɱ':'English m approximates the labiodental nasal.'}
    fr={**shared,**vowels,'ʁ':['en/r'],'ʀ':['en/r'],'r':['en/r'],'ɲ':['ja/ny'],
        'ɥ':['en/y','en/w'],'y':['zh/v'],'ø':['zh/ve'],'œ':['zh/ve'],
        'ɑ̃':['zh/ang'],'ã':['zh/ang'],'ɔ̃':['zh/ong'],'ɛ̃':['zh/eng'],'œ̃':['zh/eng'],
        'ɐ̃':['zh/ang'],'ə̃':['zh/eng'],'ɡʲ':['en/g','en/y']}
    fr_approximations={
        'ʁ':'English r substitutes for the French uvular rhotic.',
        'ɲ':'Japanese palatalized nasal approximates the French palatal nasal.',
        'ɥ':'English y+w sequence approximates the French rounded palatal glide.',
        'ø/œ':'Mandarin ve approximates rounded front mid vowels; the contrast is not modeled natively.',
        'ɑ̃/ɔ̃/ɛ̃/œ̃':'Mandarin nasal rimes approximate French nasal vowels, including a possible audible nasal coda.'}
    # Score duration carries vowel length. Consonant length is represented by
    # repeated existing consonant tokens, rather than inventing bank symbols.
    for mapping in (it,fr):
        for ipa,phones in list(mapping.items()):
            mapping[ipa+'ː']=list(phones) if ipa in vowels or ipa in ('y','ø','œ','ɑ̃','ã','ɔ̃','ɛ̃','œ̃','ɐ̃','ə̃') else phones*2
        for ipa,phones in list(mapping.items()):
            if ipa.endswith('ː'):continue
            if ipa not in vowels and ipa not in ('y','ø','œ','ɑ̃','ã','ɔ̃','ɛ̃','œ̃','ɐ̃','ə̃'):
                mapping[ipa+ipa]=phones*2
    en_vowels=['en/'+v for v in ('aa','ae','ah','ao','aw','ax','ay','eh','er','ey','ih','iy','ow','oy','uh','uw')]
    core_vowels=['ja/a','en/aa','ja/e','en/eh','en/iy','ja/o','en/ao','zh/u','en/ax','en/ih','en/uh']
    it_rewrites={v+'ˈ'+following:glide+'ˈ'+following
        for v,glide in (('i','j'),('ɪ','j'),('u','w'),('ʊ','w'))
        for following in ('a','ɑ','e','ɛ','o','ɔ')}
    it_rewrites['tʃˈao']='tʃˈaw'
    fr_rewrites={source:target for v in ('a','ɑ','e','ɛ','i','o','ɔ')
        for source,target in [('yˈ'+v,'ɥˈ'+v),('ˈy'+v,'ɥˈ'+v),('y'+v,'ɥ'+v)]}
    result={
        'en':_profile('en',inventory,acoustic_sha,en_mapping,en_vowels),
        'it':_profile('it',inventory,acoustic_sha,it,core_vowels,it_approximations,it_rewrites),
        'fr':_profile('fr',inventory,acoustic_sha,fr,[*core_vowels,'zh/v','zh/ve','zh/ang','zh/ong','zh/eng'],fr_approximations,fr_rewrites)}
    result['en']['vocalise_map']={'A':['en/aa'],'a':['ja/a'],'E':['en/eh'],'e':['ja/e'],
        'I':['en/ih'],'i':['en/iy'],'O':['en/ao'],'o':['ja/o'],'U':['en/uh'],'u':['zh/u'],
        '@':['en/ax'],'3':['en/er']}
    result['en']['vowels']+=['ja/a','ja/e','ja/o','zh/u']
    result['it']['contextual_g2p']=True
    result['fr']['contextual_g2p']=True
    # eSpeak marks French liaison/silent boundary decisions with a hyphen.
    # Its removal is a declared literal rewrite, not an unknown-phone fallback.
    result['fr']['ipa_rewrites']['-']=''
    result['it']['unstressed_glides']={'i':'j','ɪ':'j','u':'w','ʊ':'w'}
    result['it']['glide_following_vowels']='aɑeɛoɔ'
    result['it']['ipa_rewrites']['aˈiu']='ajˈu'
    return result
