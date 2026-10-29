"""Operator-installed OpenVPI DiffSinger acoustic CLI bridge (no bundled weights).

Request input follows MTA neural-singing-1. A checkpoint-pinned operator
lexicon optionally maps note-aligned syllables to bank-native phonemes.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
import sys
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

NOTES=('C','C#','D','D#','E','F','F#','G','G#','A','A#','B')


def reviewed_lexicon(path, sha256):
    """Load a pinned one-syllable-to-one-bank-token map (not general-purpose G2P).

    The lexicon must be reviewed for the installed singer phoneme inventory.
    It cannot expand one MIDI note to multiple phonemes since the acoustic score
    currently has exactly one phoneme and duration for each note.
    """
    if not path or not sha256:
        raise ValueError('A bank-specific, SHA-256-pinned lexicon is required')
    asset = safe_file(path, sha256)
    from app.ai_model_bytes import verified_model_bytes
    payload = json.loads(verified_model_bytes(asset,sha256.lower(),max_bytes=1024*1024))
    if not isinstance(payload, dict) or payload.get('schema') != 'mta-diffsinger-lexicon-1':
        raise ValueError('Unrecognized DiffSinger lexicon format')
    language = payload.get('language')
    entries = payload.get('entries')
    if language not in ('en','it','fr') or not isinstance(entries, dict) or not 1 <= len(entries) <= 20000:
        raise ValueError('Invalid DiffSinger lexicon language or entries')
    lexicon = {}
    for syllable, phoneme in entries.items():
        if not isinstance(syllable, str) or not 1 <= len(syllable) <= 60 or not syllable.isprintable():
            raise ValueError('Invalid DiffSinger lexicon syllable')
        if not isinstance(phoneme, str) or not re.fullmatch(r'[a-zA-Z@{}0-9_]{1,40}', phoneme):
            raise ValueError('Invalid bank-native phoneme token')
        key = syllable.casefold().strip()
        if not key or key in lexicon:
            raise ValueError('Duplicate or empty DiffSinger lexicon syllable')
        lexicon[key] = phoneme
    return language, lexicon


def select_score_phonemes(request, *, lexicon_path='', lexicon_sha256='',environ=None):
    """Validate source language and apply a pinned, singer-specific lexicon.

    English supports both bank-native phonemes (legacy) and an opt-in
    reviewed English lexicon. Italian and French require reviewed lexicons.
    """
    if not isinstance(request, dict):
        raise ValueError('Invalid DiffSinger score')
    if request.get('explicit_bank_phones') is True:
        from app.vocal_phonemizer import load_profile,validate_phones,profile_metadata
        environment=os.environ if environ is None else environ
        profile=load_profile(environment.get('MTA_DIFFSINGER_PHONEMES',''),
            environment.get('MTA_DIFFSINGER_PHONEMES_SHA256',''),environment.get('MTA_NEURAL_SINGER_SHA256'))
        if request.get('language') not in (profile['language'],'vocalise'):raise ValueError('Phone profile language mismatch')
        for note in request['notes']:validate_phones(note.get('phonemes'),profile['inventory'])
        return {**request,'pronunciation_profile':profile_metadata(profile)} if profile_metadata(profile) else request
    if request.get('language')=='vocalise':
        environment=os.environ if environ is None else environ
        if environment.get('MTA_DIFFSINGER_PHONEMES'):
            from app.vocal_phonemizer import load_profile,validate_phones,profile_metadata
            profile=load_profile(environment['MTA_DIFFSINGER_PHONEMES'],
                environment.get('MTA_DIFFSINGER_PHONEMES_SHA256',''),environment.get('MTA_NEURAL_SINGER_SHA256'))
            if profile.get('vocalise_map'):
                result={**request,'notes':[],'bank_language':profile.get('bank_language','en')}
                for note in request['notes']:
                    phones=note.get('phonemes')
                    if phones is None:
                        phones=profile['vocalise_map'].get(note['syllable'])
                        if phones is None and note['syllable'] in profile['inventory']:phones=[note['syllable']]
                        if phones is None:raise ValueError('Vocalise symbol absent from pinned voicebank vowel map')
                    validate_phones(phones,profile['inventory'])
                    result['notes'].append({**note,'phonemes':phones})
                if profile_metadata(profile):result['pronunciation_profile']={**profile_metadata(profile),'lyric_language':'vocalise'}
                return result
    if request.get('pronunciation') == 'espeak':
        from app.vocal_phonemizer import load_profile, phonemize_configured_score
        environment=os.environ if environ is None else environ
        profile = load_profile(environment.get('MTA_DIFFSINGER_PHONEMES', ''),
                               environment.get('MTA_DIFFSINGER_PHONEMES_SHA256', ''),environment.get('MTA_NEURAL_SINGER_SHA256'))
        if request.get('bank_profile_applied') is True:
            from app.vocal_phonemizer import validate_phones
            if request.get('language')!=profile['language']:raise ValueError('Phone profile language mismatch')
            for note in request['notes']:validate_phones(note.get('phonemes'),profile['inventory'])
            return request
        return phonemize_configured_score(request, profile, environment)
    language = request.get('language')
    if language not in ('en', 'it', 'fr', 'vocalise'):
        raise ValueError('Unsupported DiffSinger language')
    use_lexicon = language in ('it', 'fr') or request.get('use_reviewed_lexicon') is True
    if use_lexicon:
        bank_language, lexicon = reviewed_lexicon(lexicon_path, lexicon_sha256)
        if bank_language != language:
            raise ValueError('DiffSinger lexicon language does not match request')
        if request.get('bank_lexicon_applied') is True:
            if any(n.get('syllable') not in set(lexicon.values()) for n in request['notes']):raise ValueError('Phoneme outside reviewed lexicon')
            return request
        return phonemize_request(request, lexicon)
    if request.get('use_reviewed_lexicon') not in (None, False):
        raise ValueError('Invalid DiffSinger lexicon selection')
    return request


def phonemize_request(request, lexicon):
    """Replace note-aligned syllables using a reviewed bank-native lexicon."""
    if not isinstance(request, dict) or not isinstance(request.get('notes'), list):
        raise ValueError('Invalid DiffSinger score')
    converted = dict(request)
    converted['notes'] = []
    for item in request['notes']:
        if not isinstance(item, dict) or not isinstance(item.get('syllable'), str):
            raise ValueError('Invalid DiffSinger syllable')
        key = item['syllable'].casefold().strip()
        if key not in lexicon:
            raise ValueError('Syllable absent from reviewed DiffSinger lexicon: ' + key[:40])
        converted['notes'].append({**item, 'syllable': lexicon[key]})
    return converted


def ds_from_request(request):
    notes=request['notes']
    if not notes or len(notes)>20000:
        raise ValueError('Invalid DiffSinger note count')
    seq=[]; durations=[]; pitches=[]; note_durations=[]; ph_num=[]
    last=0.
    for n in notes:
        start=float(n['start_ms'])/1000
        duration=float(n['duration_ms'])/1000
        pitch=int(n['pitch'])
        ph=n['syllable']
        phones=n.get('phonemes')
        if not math.isfinite(start) or not math.isfinite(duration) or start<last-1e-4 or not 0<duration<=30 or not 0<=pitch<=127:
            raise ValueError('Invalid monophonic note sequence')
        # Phoneme input, not arbitrary orthographic words: no undocumented G2P.
        if phones is None and (not isinstance(ph,str) or not re.fullmatch(r'[a-zA-Z@{}0-9_]+',ph) or len(ph)>40):
            raise ValueError('DiffSinger requires one validated phoneme per note; configure a matching bank dictionary')
        if start>last+1e-4:
            gap=start-last
            seq.append('SP');durations.append(gap);pitches.append('rest');note_durations.append(gap);ph_num.append(1)
        if phones is None:
            phones, weights = [ph], [1.]
        else:
            weights=n.get('phoneme_weights', [1.] * len(phones))
            if (not isinstance(phones,list) or not 1 <= len(phones) <= 40
                    or any(not isinstance(p,str) or not re.fullmatch(r'[^\s\x00-\x1f\x7f]{1,40}',p) for p in phones)
                    or len(weights)!=len(phones) or any(type(w) not in (float,int) or not math.isfinite(w) or w<=0 for w in weights)):
                raise ValueError('Invalid multi-phoneme alignment')
        seq.extend(phones);durations.extend(duration*w/sum(weights) for w in weights);ph_num.append(len(phones))
        pitches.append(NOTES[pitch%12]+str(pitch//12-1));note_durations.append(duration)
        last=start+duration
    from app.vocal_expression import f0_curve
    f0=f0_curve(notes,request.get('expression',{}))
    result = {'offset':0.,'ph_num':' '.join(map(str,ph_num)),
            'f0_seq':' '.join(f'{x:.4f}' for x in f0),'f0_timestep':.005,
            'ph_seq':' '.join(seq),'ph_dur':' '.join(f'{x:.6f}' for x in durations),
            'note_seq':' '.join(pitches),'note_dur':' '.join(f'{x:.6f}' for x in note_durations)}
    if request.get('bank_language'):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,40}',request['bank_language']):raise ValueError('Invalid bank language')
        result['lang']=request['bank_language']
    from app.vocal_expression import ds_curves
    result.update(ds_curves(request.get('expression',{}),len(f0),.005))
    return result


def safe_file(path,expected_digest):
    path=Path(path)
    if not path.is_absolute() or path.is_symlink() or not path.is_file() or path.stat().st_nlink!=1:
        raise ValueError('Unsafe or missing DiffSinger asset')
    if not re.fullmatch('[a-fA-F0-9]{64}',expected_digest or ''):
        raise ValueError('Missing pinned DiffSinger asset SHA-256')
    with path.open('rb') as stream: digest=hashlib.file_digest(stream,'sha256').hexdigest()
    if digest!=expected_digest.lower():raise ValueError('DiffSinger asset checksum mismatch')
    return path


def run(request_path,output_path):
    from app.model_license_policy import evaluate_singing_components
    evaluate_singing_components()
    environment={**os.environ,'MTA_STUDIO_OFFLINE_KIND':'diffsinger'}
    model_format=os.getenv('MTA_DIFFSINGER_FORMAT','native')
    if model_format=='openutau-onnx':
        python=safe_file(os.environ['MTA_DIFFSINGER_PYTHON'],os.environ['MTA_DIFFSINGER_PYTHON_SHA256'])
        subprocess.run([str(python),str(Path(__file__).with_name('studio_offline_runner.py')),
                        str(Path(__file__).with_name('diffsinger_onnx.py')),
                        '--request',str(request_path),'--output',str(output_path)],
                       check=True,timeout=540,stdin=subprocess.DEVNULL,env=environment)
        return
    if model_format!='native':raise ValueError('Unsupported DiffSinger runtime format')
    root=Path(os.environ['MTA_DIFFSINGER_ROOT']).resolve(strict=True)
    script=root/'scripts'/'infer.py'
    if script.is_symlink() or not script.is_file():raise ValueError('DiffSinger inference script unavailable')
    python=safe_file(os.environ['MTA_DIFFSINGER_PYTHON'],os.environ['MTA_DIFFSINGER_PYTHON_SHA256'])
    acoustic=safe_file(os.environ['MTA_NEURAL_SINGER_CHECKPOINT'],os.environ['MTA_NEURAL_SINGER_SHA256'])
    vocoder=safe_file(os.environ['MTA_DIFFSINGER_VOCODER'],os.environ['MTA_DIFFSINGER_VOCODER_SHA256'])
    if not acoustic.is_relative_to(root) or not vocoder.is_relative_to(root):
        raise ValueError('DiffSinger assets must belong to installed runtime')
    exp=os.environ['MTA_DIFFSINGER_EXPERIMENT']
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',exp):raise ValueError('Invalid DiffSinger experiment name')
    experiment_dir=(root/'checkpoints'/exp).resolve()
    if not experiment_dir.is_dir() or not experiment_dir.is_relative_to(root):
        raise ValueError('Configured DiffSinger experiment not installed')
    if not acoustic.resolve().is_relative_to(experiment_dir):
        raise ValueError('Acoustic checkpoint does not belong to selected experiment')
    checkpoint_match=re.fullmatch(r'model_ckpt_steps_(\d+)\.ckpt',acoustic.name)
    if not checkpoint_match:
        raise ValueError('OpenVPI requires model_ckpt_steps_<step>.ckpt for exact checkpoint selection')
    # Config is saved flattened by OpenVPI. Reject unresolved inheritance rather
    # than hashing a vocoder which is not actually selected by the runtime.
    import yaml
    config_path=safe_file(str(experiment_dir/'config.yaml'),os.environ.get('MTA_DIFFSINGER_CONFIG_SHA256',''))
    from app.ai_model_bytes import verified_model_bytes
    config=yaml.safe_load(verified_model_bytes(config_path,os.environ['MTA_DIFFSINGER_CONFIG_SHA256'].lower(),max_bytes=1024**2))
    if not isinstance(config,dict) or config.get('base_config'):
        raise ValueError('Use a flattened OpenVPI experiment config')
    selected_vocoder=Path(config.get('vocoder_ckpt',''))
    if not selected_vocoder.is_absolute():selected_vocoder=root/selected_vocoder
    if selected_vocoder.resolve()!=vocoder.resolve():
        raise ValueError('Verified vocoder does not match the selected experiment config')
    request=json.loads(Path(request_path).read_text())
    if request.get('schema')!='mta-neural-singing-1':raise ValueError('Unsupported request schema')
    request = select_score_phonemes(
        request,
        lexicon_path=os.environ.get('MTA_DIFFSINGER_LEXICON', ''),
        lexicon_sha256=os.environ.get('MTA_DIFFSINGER_LEXICON_SHA256', ''),
    )
    ds=ds_from_request(request)
    for feature in ('energy','breathiness','voicing','tension'):
        enabled=bool(config.get('use_'+feature+'_embed'))
        if enabled != (feature in ds):
            raise ValueError('Bank '+feature+' embedding and supplied expression curve must match')
    for feature,enabled in (('gender','use_key_shift_embed'),('velocity','use_speed_embed')):
        if feature in ds and not config.get(enabled):
            raise ValueError('Selected bank does not support '+feature)
    expected_seconds=sum(float(x) for x in ds['note_dur'].split())
    if not 0 < expected_seconds <= 600:
        raise ValueError('DiffSinger score exceeds supported duration')
    import soundfile as sf
    import numpy as np
    with tempfile.TemporaryDirectory(prefix='mta-diffsinger-') as tmp:
        tmp=Path(tmp);project=tmp/'singer.ds';project.write_text(json.dumps(ds))
        out=tmp/'render';out.mkdir()
        subprocess.run([str(python),str(Path(__file__).with_name('studio_offline_runner.py')),str(script),'acoustic',str(project),'--exp',exp,'--ckpt',checkpoint_match[1],'--out',str(out),'--title','singer'],
                       cwd=root,env=environment,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                       timeout=540,check=True)
        files=list(out.glob('*.wav'))
        if len(files)!=1 or files[0].is_symlink() or not files[0].is_file():
            raise RuntimeError('DiffSinger must produce exactly one WAV')
        info=sf.info(files[0])
        if not 0 < info.samplerate <= 192000 or not 1 <= info.channels <= 2 or not 0 < info.duration <= min(610,expected_seconds+10):
            raise ValueError('Invalid or oversized generated WAV')
        data,rate=sf.read(files[0],dtype='float32')
        if data.ndim==2:data=data.mean(axis=1)
        if rate<=0 or rate>384000 or len(data)==0 or not np.isfinite(data).all():raise ValueError('Invalid generated WAV')
        actual_seconds=len(data)/rate
        if actual_seconds>min(610,expected_seconds+10) or actual_seconds<max(0.05,expected_seconds*0.5):
            raise ValueError('Neural output duration does not match the score')
        from scipy.signal import resample_poly
        from math import gcd
        divisor=gcd(rate,48000)
        converted=resample_poly(data,48000//divisor,rate//divisor).astype('float32')
        if not np.isfinite(converted).all() or float(np.max(np.abs(converted)))>1.01:
            raise ValueError('Invalid neural output amplitude')
        sf.write(output_path,converted,48000,subtype='PCM_24')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--request',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();run(args.request,args.output)
