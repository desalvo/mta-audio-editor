"""Real IT/EN/FR G2P through optional eSpeak NG and a reviewed bank IPA map.

No guessed universal phone alphabet. A pinned profile must cover each IPA unit
and every emitted phone must exist in the bank's pinned phoneme inventory.
The optional GPL eSpeak runtime/data are external, not redistributed by MTA.
"""
import ctypes as C
from functools import lru_cache
import json
import os
import re
import threading
import unicodedata

_LOCK = threading.Lock()
TOKEN = re.compile(r'[^\s\x00-\x1f\x7f]{1,40}')


def load_profile(path, digest,bank_sha256=None):
    from .diffsinger_bridge import safe_file
    asset = safe_file(path, digest)
    if asset.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Phonemizer profile exceeds size budget')
    profile = json.loads(asset.read_text(encoding='utf-8'))
    if profile.get('schema') != 'mta-bank-phonemes-1' or profile.get('language') not in ('en', 'it', 'fr'):
        raise ValueError('Invalid bank phonemizer profile')
    bank_digest=profile.get('bank_sha256','')
    if not isinstance(bank_digest,str) or not re.fullmatch(r'[a-f0-9]{64}',bank_digest):
        raise ValueError('Phonemizer profile must identify its reviewed acoustic checkpoint SHA-256')
    configured=bank_sha256 if bank_sha256 is not None else os.environ.get('MTA_NEURAL_SINGER_SHA256')
    if configured and bank_digest!=configured.lower():
        raise ValueError('Phonemizer profile belongs to a different voicebank checkpoint')
    bank_language=profile.get('bank_language')
    if bank_language is not None and (not isinstance(bank_language,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,40}',bank_language)):
        raise ValueError('Invalid bank language name')
    inventory = profile.get('inventory')
    if not isinstance(inventory, list) or not 1 <= len(inventory) <= 2000 or any(not isinstance(p, str) or not TOKEN.fullmatch(p) for p in inventory):
        raise ValueError('Invalid bank phoneme inventory')
    if len(set(inventory)) != len(inventory) or 'SP' not in inventory:
        raise ValueError('Inventory must contain unique phones including SP')
    mapping = profile.get('ipa_map')
    if not isinstance(mapping, dict) or not 1 <= len(mapping) <= 2000:
        raise ValueError('Missing bank IPA mapping')
    for ipa, phones in mapping.items():
        if not isinstance(ipa, str) or not ipa or len(ipa) > 20 or not ipa.isprintable() or any(c.isspace() for c in ipa):
            raise ValueError('Invalid IPA mapping key')
        validate_phones(phones, inventory)
    vowels = profile.get('vowels')
    if not isinstance(vowels, list) or not vowels or any(p not in inventory for p in vowels):
        raise ValueError('Declare bank vowel phones for duration allocation')
    vocalises=profile.get('vocalise_map',{})
    if not isinstance(vocalises,dict) or len(vocalises)>100:
        raise ValueError('Invalid vocalise map')
    for vowel,phones in vocalises.items():
        if not isinstance(vowel,str) or not 1<=len(vowel)<=40 or not vowel.isprintable():
            raise ValueError('Invalid vocalise symbol')
        validate_phones(phones,inventory)
        if any(phone not in vowels for phone in phones):raise ValueError('Vocalise map requires declared vowel phones')
    rewrites=profile.get('ipa_rewrites',{})
    if (not isinstance(rewrites,dict) or len(rewrites)>100
            or any(not isinstance(k,str) or not 1<=len(k)<=40 or not k.isprintable()
                   or not isinstance(v,str) or not 0<=len(v)<=40 or (v and not v.isprintable()) for k,v in rewrites.items())):
        raise ValueError('Invalid literal IPA rewrite table')
    glides=profile.get('unstressed_glides',{})
    if (not isinstance(glides,dict) or len(glides)>20
            or any(not isinstance(k,str) or len(k)!=1 or not isinstance(v,str) or len(v)!=1 for k,v in glides.items())
            or not isinstance(profile.get('glide_following_vowels',''),str)
            or len(profile.get('glide_following_vowels',''))>40):
        raise ValueError('Invalid profile glide rules')
    if type(profile.get('contextual_g2p', False)) is not bool:
        raise ValueError('Invalid contextual G2P selection')
    mode=profile.get('pronunciation_mode')
    if mode is not None:
        if mode not in ('native-inventory','cross-language'):
            raise ValueError('Invalid pronunciation profile mode')
        languages=profile.get('acoustic_languages')
        if (not isinstance(languages,list) or not 1<=len(languages)<=20
                or any(not isinstance(l,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,40}',l) for l in languages)):
            raise ValueError('Declare profile acoustic languages')
        approximations=profile.get('approximations',{})
        if (not isinstance(approximations,dict) or len(approximations)>100
                or any(not isinstance(k,str) or not 1<=len(k)<=80 or not isinstance(v,str) or not 1<=len(v)<=400
                       for k,v in approximations.items())):
            raise ValueError('Invalid pronunciation approximation disclosure')
        if mode=='cross-language' and (not approximations or not isinstance(profile.get('notes'),str)
                                       or not 1<=len(profile['notes'])<=1000):
            raise ValueError('Cross-language profile requires approximation disclosure')
    # The profile is an operator-reviewed mapping, not an automatic rights grant.
    return profile



def profile_metadata(profile):
    """Small pinned pronunciation disclosure carried into each singer receipt."""
    if not profile.get('pronunciation_mode'):return {}
    return {'lyric_language':profile['language'],'mode':profile['pronunciation_mode'],
            'acoustic_languages':profile['acoustic_languages'],
            'approximations':profile.get('approximations',{}),'ipa_rewrites':profile.get('ipa_rewrites',{}),
            'unstressed_glides':profile.get('unstressed_glides',{}),
            'glide_following_vowels':profile.get('glide_following_vowels',''),
            'contextual_g2p':profile.get('contextual_g2p',False),
            'note':profile.get('notes','')}


def validate_phones(phones, inventory):
    if not isinstance(phones, list) or not 1 <= len(phones) <= 40 or any(not isinstance(p, str) or p not in inventory for p in phones):
        raise ValueError('Phoneme missing from reviewed voicebank inventory')


@lru_cache(maxsize=1)
def _engine():
    library = os.getenv('MTA_ESPEAK_LIBRARY', '')
    data = os.getenv('MTA_ESPEAK_DATA', '')
    if not library:
        try:
            import espeakng_loader
            library, data = str(espeakng_loader.get_library_path()), str(espeakng_loader.get_data_path())
        except ImportError as exc:
            raise RuntimeError('Install optional espeakng-loader or configure eSpeak NG library/data') from exc
    from pathlib import Path
    if not Path(library).is_absolute() or not Path(library).is_file() or not Path(data).is_absolute() or not Path(data).is_dir():
        raise ValueError('eSpeak library/data must be installed absolute paths')
    lib = C.CDLL(library)
    lib.espeak_Initialize.argtypes = [C.c_int, C.c_int, C.c_char_p, C.c_int]
    lib.espeak_Initialize.restype = C.c_int
    lib.espeak_SetVoiceByName.argtypes = [C.c_char_p]
    lib.espeak_SetVoiceByName.restype = C.c_int
    lib.espeak_TextToPhonemes.argtypes = [C.POINTER(C.c_void_p), C.c_int, C.c_int]
    lib.espeak_TextToPhonemes.restype = C.c_char_p
    if lib.espeak_Initialize(2, 0, data.encode(), 0x8000) <= 0:
        raise RuntimeError('Cannot initialize eSpeak NG phonemizer')
    return lib


def ipa_for_text(text, language):
    if language not in ('en', 'it', 'fr') or not isinstance(text, str) or not 1 <= len(text) <= 5000:
        raise ValueError('Invalid phonemizer text/language')
    if any(not (c.isalpha() or c in " '-’") for c in text):
        raise ValueError('Use lyric words or syllables without phoneme/markup commands')
    with _LOCK:
        lib = _engine()
        if lib.espeak_SetVoiceByName({'en': b'en-us', 'it': b'it', 'fr': b'fr'}[language]):
            raise RuntimeError('Requested eSpeak language is not installed')
        buffer = C.create_string_buffer(unicodedata.normalize('NFC', text).encode('utf-8'))
        pointer = C.c_void_p(C.addressof(buffer))
        chunks = []
        for _ in range(100):
            if not pointer.value:
                break
            previous = pointer.value
            value = lib.espeak_TextToPhonemes(C.byref(pointer), 1, 2)
            if value:
                chunks.append(value.decode('utf-8'))
            if pointer.value == previous:
                raise RuntimeError('Phonemizer made no progress')
        else:
            raise ValueError('Phonemizer output exceeds clause budget')
    return ' '.join(chunks)


def map_ipa(ipa, profile):
    # Stress is not a phoneme. Length and nasalization remain in the mapping.
    source = unicodedata.normalize('NFC', ipa)
    if len(source)>4000:raise ValueError('IPA source exceeds profile mapping budget')
    for before,after in sorted(profile.get('ipa_rewrites',{}).items(),key=lambda item:(-len(item[0]),item[0])):
        source=source.replace(before,after)
        if len(source)>4000:raise ValueError('IPA rewrite exceeds profile mapping budget')
    glides=profile.get('unstressed_glides',{});following=profile.get('glide_following_vowels','')
    if glides:
        units=list(source)
        for i,char in enumerate(source):
            if char not in glides or (i and source[i-1] in 'ˈˌ'):continue
            next_index=i+1
            if next_index<len(source) and source[next_index] in 'ˈˌ':next_index+=1
            if next_index<len(source) and source[next_index] in following:units[i]=glides[char]
        source=''.join(units)
    source=source.replace('ˈ', '').replace('ˌ', '')
    mapping = profile['ipa_map']
    keys = sorted(mapping, key=lambda s: (-len(s), s))
    phones, index = [], 0
    while index < len(source):
        if source[index].isspace():
            index += 1
            continue
        key = next((key for key in keys if source.startswith(key, index)), None)
        if key is None:
            raise ValueError('IPA absent from reviewed bank mapping: ' + source[index:index + 16])
        phones.extend(mapping[key]); index += len(key)
        if len(phones) > 40:
            raise ValueError('Too many phonemes for one note; split lyrics across notes')
    validate_phones(phones, profile['inventory'])
    return phones


def phonemize_score(request, profile):
    if request['language'] != profile['language']:
        raise ValueError('Voicebank phonemizer language mismatch')
    if request.get('lyric_text'):return align_text(request,profile)
    result = dict(request); result['notes'] = []
    if profile_metadata(profile):result['pronunciation_profile']=profile_metadata(profile)
    if profile.get('bank_language'):result['bank_language']=profile['bank_language']
    cache = {}
    for note in request['notes']:
        text = note['syllable']
        if text not in cache:
            cache[text] = map_ipa(ipa_for_text(text, request['language']), profile)
        phones = cache[text]
        nuclei = [i for i, phone in enumerate(phones) if phone in profile['vowels']]
        if len(nuclei) != 1:
            raise ValueError('Assign one vowel nucleus/syllable to each MIDI note')
        # Explicit deterministic alignment: sustain vowel, bounded consonants.
        weights = [1. if i == nuclei[0] else .12 for i in range(len(phones))]
        result['notes'].append({**note, 'phonemes': phones, 'phoneme_weights': weights})
    return result


def align_text(request,profile):
    """Deterministic text-to-score alignment, never forced acoustic alignment.

    Syllables follow reviewed bank vowel nuclei; exact note count or explicit
    melisma counts are required. The resulting mapping remains reviewable.
    """
    text=request.get('lyric_text','')
    if not isinstance(text,str) or not 1<=len(text)<=5000:raise ValueError('Lyric text must contain 1–5000 characters')
    words=re.findall(r"[^\W\d_]+(?:['’][^\W\d_]+)*",text,flags=re.UNICODE)
    if not words:raise ValueError('No lyric words to align')
    units=[]
    vowels=set(profile['vowels'])
    if profile.get('contextual_g2p'):
        ipa_words=ipa_for_text(' '.join(words),request['language']).split()
        if len(ipa_words)!=len(words):
            raise ValueError('Contextual G2P word boundaries differ; review lyrics or provide explicit bank phones')
    else:
        ipa_words=[ipa_for_text(word,request['language']) for word in words]
    for word_index,(word,ipa) in enumerate(zip(words,ipa_words)):
        phones=map_ipa(ipa,profile)
        nuclei=[i for i,p in enumerate(phones) if p in vowels]
        if not nuclei:raise ValueError('Lyric word has no supported vowel nucleus: '+word)
        # Keep onset clusters with the following vowel. The reviewed inventory
        # defines nuclei; articulation/linguistic quality still requires review.
        boundaries=[0]+[nuclei[i-1]+1 for i in range(1,len(nuclei))]+[len(phones)]
        for syllable_index,(left,right) in enumerate(zip(boundaries,boundaries[1:])):
            unit=phones[left:right]
            units.append((word_index,word,syllable_index,unit))
    counts=request.get('melisma_counts') or [1]*len(units)
    if (len(counts)!=len(units) or any(type(n) is not int or not 1<=n<=100 for n in counts)
            or sum(counts)!=len(request['notes'])):
        raise ValueError('Text syllable count must match notes; supply one explicit melisma count per syllable when needed')
    result=dict(request);result['notes']=[];index=0
    if profile_metadata(profile):result['pronunciation_profile']=profile_metadata(profile)
    for (word_index,word,syllable_index,phones),count in zip(units,counts):
        for tied in range(count):
            selected=phones if tied==0 else [next(p for p in phones if p in vowels)]
            result['notes'].append({**request['notes'][index],'syllable':word,'word_index':word_index,
                'word':word,'syllable_index':syllable_index,'phonemes':selected,
                'phoneme_weights':[1. if p in vowels else .12 for p in selected]})
            index+=1
    if profile.get('bank_language'):result['bank_language']=profile['bank_language']
    return result


def phonemize_configured_score(request, profile, environ):
    """Use local G2P, or the same pinned external runtime as the acoustic bank.

    Only dependency absence selects the external path. A broken explicitly
    configured local library fails visibly rather than silently changing G2P.
    The child receives a score, never a command or client-selected interpreter.
    """
    import importlib.util
    from pathlib import Path
    import subprocess
    local = environ.get('MTA_ESPEAK_LIBRARY') or importlib.util.find_spec('espeakng_loader') is not None
    if local:
        return phonemize_score(request, profile)
    if not environ.get('MTA_DIFFSINGER_PYTHON'):
        return phonemize_score(request, profile)
    from .diffsinger_bridge import safe_file
    python = safe_file(environ['MTA_DIFFSINGER_PYTHON'], environ.get('MTA_DIFFSINGER_PYTHON_SHA256', ''))
    payload = json.dumps(request, ensure_ascii=False, allow_nan=False).encode()
    limit = 4 * 1024 * 1024
    if len(payload) > limit:
        raise ValueError('G2P request exceeds size budget')
    command = [str(python), '-I', str(Path(__file__).with_name('vocal_g2p_bridge.py')),
               '--profile', environ.get('MTA_DIFFSINGER_PHONEMES', ''),
               '--profile-sha256', environ.get('MTA_DIFFSINGER_PHONEMES_SHA256', ''),
               '--bank-sha256', profile['bank_sha256']]
    try:
        completed = subprocess.run(command, input=payload, capture_output=True, timeout=60,
                                   env={**os.environ, **environ, 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1'},
                                   check=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError('Pinned DiffSinger runtime lyric G2P failed; install requirements-studio-phonemizer.txt '
                           'in that runtime and verify its eSpeak library/data') from exc
    if len(completed.stdout) > limit:
        raise ValueError('G2P response exceeds size budget')
    result = json.loads(completed.stdout)
    if (not isinstance(result, dict) or len(result.get('notes', [])) != len(request['notes'])
            or result.get('language') != request['language']):
        raise ValueError('Invalid G2P runtime result')
    for original, converted in zip(request['notes'], result['notes']):
        for name in ('id', 'pitch', 'start_ms', 'duration_ms', 'velocity'):
            if converted.get(name) != original.get(name):
                raise ValueError('G2P runtime changed score timing or musical data')
        validate_phones(converted.get('phonemes'), profile['inventory'])
    if profile_metadata(profile):
        result['pronunciation_profile'] = profile_metadata(profile)
    return result


def word_regions(notes):
    rows=[];last_syllable=None
    for index,note in enumerate(notes):
        if 'word_index' not in note:continue
        end=float(note['start_ms'])+float(note['duration_ms']);syllable=note['syllable_index']
        if rows and rows[-1][0]==note['word_index']:
            rows[-1][3]=end;rows[-1][5]+=1;rows[-1][7].append(note.get('id',''))
            if syllable==last_syllable:rows[-1][6][-1]+=1
            else:rows[-1][6].append(1)
        else:rows.append([note['word_index'],note['word'],float(note['start_ms']),end,index,1,[1],[note.get('id','')]])
        last_syllable=syllable
    return rows


def syllable_regions(notes):
    """Compact editable bank-phone groups with stable note identities."""
    rows=[];previous=None
    for note in notes:
        if 'word_index' not in note:continue
        key=(note['word_index'],note['syllable_index'])
        if key!=previous:
            rows.append({'word':note['word'],'syllable_index':note['syllable_index'],
                         'note_ids':[],'phones':[]})
        rows[-1]['note_ids'].append(note.get('id',''))
        rows[-1]['phones'].append(note['phonemes'])
        previous=key
    return rows
