"""Actual CPU bridge/G2P QA; outputs are not native-pronunciation certificates.

Use an already installed, complete and licensed bundle; this script does not
install models, change policy/admission, or grant distribution/service rights.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT))
from app.studio_asset_registry import validate_manifest
from app.vocal_phonemizer import load_profile,phonemize_score


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle-root',type=Path,required=True)
    parser.add_argument('--manifest-sha256',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();root=args.bundle_root.resolve();output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    manifest_path=root/'manifest.json';raw=manifest_path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=args.manifest_sha256:raise ValueError('Unexpected manifest SHA-256')
    manifest=validate_manifest(json.loads(raw));bindings=manifest['bindings'];files=manifest['files']
    python=Path(sys.executable).absolute()
    if python.is_symlink():raise ValueError('Use a copied regular interpreter for pinned execution')
    env={**os.environ,'MTA_DIFFSINGER_FORMAT':'openutau-onnx',
        'MTA_DIFFSINGER_PYTHON':str(python),'MTA_DIFFSINGER_PYTHON_SHA256':hashlib.sha256(python.read_bytes()).hexdigest(),
        'MTA_DIFFSINGER_ONNX_INVENTORY':str(manifest_path),'MTA_DIFFSINGER_ONNX_INVENTORY_SHA256':args.manifest_sha256,
        'MTA_NEURAL_SINGER_CHECKPOINT':str(root/bindings['acoustic']),'MTA_NEURAL_SINGER_SHA256':files[bindings['acoustic']]['sha256'],
        'MTA_DIFFSINGER_VOCODER':str(root/bindings['vocoder']),'MTA_DIFFSINGER_VOCODER_SHA256':files[bindings['vocoder']]['sha256'],
        'MTA_DIFFSINGER_ONNX_STEPS':'32','PYTHONDONTWRITEBYTECODE':'1'}
    cases=[
        ('it-text','it','ciao amore',[1,1,1,1]),
        ('it-palatals','it','gli gnocchi',[1,1,1]),
        ('it-melisma','it','ciao amore',[1,2,1,1]),
        ('fr-text','fr','bonjour lune',[1,1,1]),
        ('fr-nasal-rounded','fr','pain cœur nuit',[1,1,1]),
        ('fr-melisma','fr','bonjour lune',[1,2,1]),
        ('en-regression','en','hello world',[1,1,1]),
        ('vocalise-default','vocalise','',[1,1,1]),
    ]
    rows=[]
    import numpy as np
    import soundfile as sf
    for name,language,text,counts in cases:
        profile_path=manifest['language_bindings'].get(language,{'phonemes':bindings['phonemes']})['phonemes'];entry=files[profile_path]
        env['MTA_DIFFSINGER_PHONEMES']=str(root/profile_path);env['MTA_DIFFSINGER_PHONEMES_SHA256']=entry['sha256']
        profile=load_profile(str(root/profile_path),entry['sha256'],env['MTA_NEURAL_SINGER_SHA256'])
        notes=[{'id':'n'+str(i),'pitch':[60,64,67,65,69][i%5],'start_ms':600*i,'duration_ms':600,'velocity':96,'syllable':'la'} for i in range(sum(counts))]
        request={'schema':'mta-neural-singing-1','language':language,'pronunciation':'espeak',
            'model':'diffsinger-qixuan','checkpoint':env['MTA_NEURAL_SINGER_CHECKPOINT'],
            'lyric_text':text,'melisma_counts':counts,'notes':notes,'expression':{}}
        if language=='vocalise':
            from app.diffsinger_bridge import select_score_phonemes
            request['pronunciation']='native';request['lyric_text']='';request['melisma_counts']=[]
            for note in request['notes']:note['syllable']='A'
            expected=select_score_phonemes(request,environ=env)
        else:expected=phonemize_score(request,profile)
        request_path=output/('r210-qixuan-'+name+'-request.json');request_path.write_text(json.dumps(request,ensure_ascii=False,indent=2)+'\n')
        wav=output/('r210-qixuan-'+name+'.wav');log=output/('r210-qixuan-'+name+'.log')
        if wav.exists():raise FileExistsError('Choose a new QA output directory')
        started=time.monotonic()
        with log.open('wb') as stream:
            subprocess.run([str(python),str(PROJECT/'app/diffsinger_bridge.py'),'--request',str(request_path),'--output',str(wav)],env=env,check=True,timeout=600,stdout=stream,stderr=subprocess.STDOUT)
        samples,rate=sf.read(wav,always_2d=True,dtype='float32');info=sf.info(wav)
        peak=float(np.max(np.abs(samples)));rms=float(np.sqrt(np.mean(samples*samples)))
        if rate!=48000 or samples.shape[1]!=1 or not np.isfinite(samples).all() or not 1e-5<peak<=1.01 or rms<1e-6:
            raise ValueError('Invalid/nearly silent inference audio')
        if abs(info.duration-.6*len(notes))>.025:raise ValueError('Output is not aligned to actual score duration')
        row={'case':name,'language':language,'lyric_text':text,'notes':len(notes),'seconds':info.duration,
            'frames':info.frames,'sample_rate':rate,'peak':peak,'rms':rms,'wall_seconds':time.monotonic()-started,
            'sha256':hashlib.sha256(wav.read_bytes()).hexdigest(),'profile_sha256':entry['sha256'],
            'pronunciation_mode':profile['pronunciation_mode'],
            'phones':[note['phonemes'] for note in expected['notes']],
            'projection_disclosure':expected.get('pronunciation_profile',{}),
            'actual_neural_inference':True,'fixture_substitution':False,'target_listening_certified':False}
        rows.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
        (output/'r210-qixuan-itfr-real-audio-audit.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
    return 0


if __name__=='__main__':raise SystemExit(main())
