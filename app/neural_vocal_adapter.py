"""Fail-closed operator-installed neural singing contract.

The executable and checkpoint are deployment-controlled, never supplied by API
clients. This adapter does not bundle model weights or assert their license.
"""
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess


def checked_assets():
    executable = Path(os.environ.get('MTA_NEURAL_SINGER_EXECUTABLE',''))
    checkpoint = Path(os.environ.get('MTA_NEURAL_SINGER_CHECKPOINT',''))
    checksum = os.environ.get('MTA_NEURAL_SINGER_SHA256','').lower()
    if not all([executable.is_absolute(),checkpoint.is_absolute(),len(checksum)==64]):
        raise RuntimeError('Neural singing requires an operator-installed executable, checkpoint and pinned SHA-256')
    if any(c not in '0123456789abcdef' for c in checksum):raise ValueError('Invalid checkpoint digest')
    for path in (executable,checkpoint):
        if path.is_symlink() or not path.is_file() or not stat.S_ISREG(path.stat().st_mode) or path.stat().st_nlink!=1:
            raise ValueError('Unsafe neural singing asset')
    if not os.access(executable,os.X_OK):raise ValueError('Neural singer is not executable')
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest()!=checksum:raise ValueError('Neural singer checkpoint integrity mismatch')
    return executable,checkpoint,checksum


def render_neural(score,cfg,output,progress):
    from .model_license_policy import evaluate_model
    from .vocal_synthesis import validate_voice_lyrics,ordered_voice_events
    from .music_interchange import MusicResult
    from .vocal_conversion import convert
    import soundfile as sf
    import numpy as np
    validate_voice_lyrics(score.music.parts,cfg)
    output=Path(output);artifacts=[];receipts=[];parts=[]
    for index,part in enumerate(score.music.parts):
        environment=dict(os.environ);bundle={}
        asset_id=cfg.neural_banks[index] if cfg.neural_banks else cfg.neural_bank
        if asset_id:
            from .studio_asset_registry import singer_environment
            managed,bundle=singer_environment(asset_id,cfg.language)
            environment.update(managed)
        model=environment.get('MTA_NEURAL_SINGER_POLICY_MODEL','')
        if not model:raise RuntimeError('Configure a licensed neural singing model identity')
        evaluate_model(model)
        if cfg.backend=='diffsinger':
            evaluate_model(environment.get('MTA_DIFFSINGER_VOCODER_POLICY_MODEL','diffsinger-vocoder'))
            from .diffsinger_bridge import safe_file
            checkpoint=safe_file(environment.get('MTA_NEURAL_SINGER_CHECKPOINT',''),environment.get('MTA_NEURAL_SINGER_SHA256',''))
            executable=Path(__file__).with_name('diffsinger_bridge.py')
            digest=environment['MTA_NEURAL_SINGER_SHA256'].lower()
        else:executable,checkpoint,digest=checked_assets()
        lyrics=cfg.voice_syllables[index] if cfg.voice_syllables else cfg.syllables
        events=ordered_voice_events(part,lyrics if cfg.language!='vocalise' else [])
        request={'schema':'mta-neural-singing-1','model':model,'checkpoint':str(checkpoint),
                 'language':cfg.language,'singer_index':index,
                 'pronunciation':cfg.pronunciation,'use_reviewed_lexicon':cfg.pronunciation=='lexicon',
                 'expression':cfg.expression.model_dump(exclude_unset=True),'lyric_text':cfg.lyric_text,'melisma_counts':cfg.melisma_counts,
                 'notes':[{'id':note.id,'pitch':int(note.pitch),'start_ms':float(note.start_ms),'duration_ms':float(note.duration_ms),
                           'velocity':int(note.velocity),'syllable':lyric or cfg.vocalise} for note,lyric in events]}
        if (bundle.get('pronunciation_modes',{}).get(cfg.language)=='cross-language'
                and cfg.pronunciation=='native' and not cfg.explicit_phones):
            request['pronunciation']='espeak'
        if bundle.get('format')=='openutau-onnx':
            request['expression']={**bundle.get('expression_defaults',{}),**request['expression']}
        if cfg.explicit_phones:
            if len(cfg.explicit_phones)!=len(request['notes']):raise ValueError('Provide one explicit phone sequence per selected note')
            request['explicit_bank_phones']=True
            for note,phones in zip(request['notes'],cfg.explicit_phones):note['phonemes']=phones
        if cfg.backend=='diffsinger':
            from .diffsinger_bridge import select_score_phonemes
            request=select_score_phonemes(request,lexicon_path=environment.get('MTA_DIFFSINGER_LEXICON',''),
                lexicon_sha256=environment.get('MTA_DIFFSINGER_LEXICON_SHA256',''),environ=environment)
            if asset_id:
                from .vocal_phonemizer import load_profile,validate_phones
                profile=load_profile(environment['MTA_DIFFSINGER_PHONEMES'],environment['MTA_DIFFSINGER_PHONEMES_SHA256'],digest)
                for note in request['notes']:validate_phones(note.get('phonemes',[note['syllable']]),profile['inventory'])
            if request['pronunciation']=='espeak':request['bank_profile_applied']=True
            elif cfg.pronunciation=='lexicon' or cfg.language in ('it','fr'):request['bank_lexicon_applied']=True
        source=output/f'neural-input-{index}.json';source.write_text(json.dumps(request,allow_nan=False))
        destination=output/f'voice-{index}.wav'
        progress('neural-singing',f'Neural singer {index+1}/{len(score.music.parts)}')
        try:
            command=([os.sys.executable,str(executable)] if cfg.backend=='diffsinger' else [str(executable)])
            subprocess.run(command+['--request',str(source),'--output',str(destination)],env=environment,
                           cwd=str(output),stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL,timeout=600,check=True)
        finally:source.unlink(missing_ok=True)
        if destination.is_symlink() or not destination.is_file() or destination.stat().st_nlink!=1:
            raise RuntimeError('Neural singer produced no safe audio file')
        info=sf.info(str(destination))
        if info.format!='WAV' or info.channels!=1 or info.samplerate!=48000 or not 0<info.duration<=610:
            raise ValueError('Invalid neural singing output WAV')
        audio,_=sf.read(str(destination),dtype='float32')
        if not np.isfinite(audio).all() or float(np.max(np.abs(audio)))>1.01:
            raise ValueError('Neural singing output is invalid or clipped')
        from .vocal_expression import apply_dynamics
        audio=apply_dynamics(audio,48000,request['notes'],request['expression'],cfg.gain)
        sf.write(str(destination),audio,48000,subtype='PCM_24')
        conversion=convert(destination,cfg.conversion.model_dump(),progress)
        artifacts.append((destination,'audio/wav'))
        parts.append(part.model_copy(update={'source_model':model}))
        from .vocal_phonemizer import word_regions,syllable_regions
        receipts.append({'model':model,'asset_id':asset_id,'checkpoint_sha256':digest,'conversion':conversion,
                         'model_format':bundle.get('format','native'),'effective_expression':request['expression'],
                         'pronunciation_profile':request.get('pronunciation_profile',{}),
                         'effective_pronunciation':request['pronunciation'],
                         'phone_profile_sha256':environment.get('MTA_DIFFSINGER_PHONEMES_SHA256',''),
                         'word_regions':word_regions(request['notes']),'syllable_regions':syllable_regions(request['notes'])})
    pronunciation_warnings=list(dict.fromkeys(r['pronunciation_profile']['note'] for r in receipts
        if r.get('pronunciation_profile',{}).get('mode')=='cross-language'))
    result=MusicResult(parts=parts,offset_ms=score.music.offset_ms,warnings=score.music.warnings+pronunciation_warnings+[
        'Neural model output requires pronunciation and musical review; no quality or hardware certification is implied.'])
    path=output/'music.json';path.write_text(result.model_dump_json());artifacts.append((path,'application/json'))
    path=output/'singing.json';path.write_text(json.dumps({'backend':cfg.backend,'singers':receipts,
        'model':receipts[0]['model'],'checkpoint_sha256':receipts[0]['checkpoint_sha256'],
        'rights_attested_by_operator':True,'settings':cfg.model_dump(),
        'expression_method':'score F0/vibrato, bank variance embeddings and explicit PCM dynamics'}))
    artifacts.append((path,'application/json'))
    return artifacts
