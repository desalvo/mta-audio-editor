"""Pinned OpenUtau DiffSinger acoustic/vocoder inference, without weight conversion.

Uses exported end-to-end ONNX graphs, explicit phoneme durations and score F0.
Variance/pitch predictors are not claimed: curves/defaults are declared controls.
"""
import json
import os
from pathlib import Path,PurePosixPath
import sys

os.environ['ORT_DISABLE_TELEMETRY']='1'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def inventory():
    from app.diffsinger_bridge import safe_file
    from app.studio_asset_registry import validate_manifest,relative
    from app.ai_model_bytes import verified_model_bytes
    path=Path(os.environ['MTA_DIFFSINGER_ONNX_INVENTORY'])
    if not path.is_absolute():raise ValueError('Absolute ONNX inventory required')
    raw=verified_model_bytes(path,os.environ['MTA_DIFFSINGER_ONNX_INVENTORY_SHA256'].lower(),max_bytes=4*1024**2)
    value=validate_manifest(json.loads(raw))
    if value['kind']!='diffsinger' or value.get('format')!='openutau-onnx':raise ValueError('Wrong ONNX inventory kind')
    root=path.parent
    def asset(name):
        relative(name)
        if name not in value['files']:raise ValueError('Unpinned ONNX dependency')
        target=root/name
        if not target.resolve().is_relative_to(root.resolve()):raise ValueError('ONNX dependency outside bundle')
        entry=value['files'][name]
        result=safe_file(str(target),entry['sha256'])
        if result.stat().st_size!=entry['bytes']:raise ValueError('ONNX dependency size mismatch')
        return result
    # Includes notices and the complete author package, not just selected weights.
    for name in value['files']:asset(name)
    return value,asset


def asset_bytes(value,asset,name,*,limit):
    """Parse the exact bytes pinned by the verified inventory, never a reopened path."""
    from app.ai_model_bytes import verified_model_bytes
    path=asset(name)
    return verified_model_bytes(path,value['files'][name]['sha256'],max_bytes=limit)


def token_inputs(phones,mapping,languages,default_language):
    """Shared multilingual token IDs need language IDs; unique IDs use zero."""
    import numpy as np
    if (not isinstance(mapping,dict) or not 1<=len(mapping)<=2000
            or any(not isinstance(k,str) or type(v) is not int or not 1<=v<=65535 for k,v in mapping.items())
            or not isinstance(languages,dict) or any(type(v) is not int or not 1<=v<=1000 for v in languages.values())):
        raise ValueError('Invalid ONNX phone/language inventory')
    groups={}
    for key,value in mapping.items():
        if '/' in key:groups.setdefault(value,set()).add(key.split('/')[0])
    ids=[];lang=[]
    for phone in phones:
        if phone not in mapping:phone=default_language+'/'+phone
        if phone not in mapping:raise ValueError('Phone missing from ONNX bank: '+phone)
        ids.append(mapping[phone])
        language=phone.split('/')[0] if '/' in phone else ''
        if len(groups.get(mapping[phone],set()))>1:
            if language not in languages:raise ValueError('Unknown ONNX language')
            lang.append(languages[language])
        else:lang.append(0)
    return np.array([ids],np.int64),np.array([lang],np.int64)


def acoustic_inputs(ds,config,phones,languages,defaults,steps=32):
    import numpy as np
    dt=config['hop_size']/config['sample_rate']
    durations=np.array([float(x) for x in ds['ph_dur'].split()],np.float64)
    phone_list=ds['ph_seq'].split()
    if (not 1<=len(phone_list)<=20000 or len(durations)!=len(phone_list)
            or not np.isfinite(durations).all() or np.min(durations)<=0 or not 0<durations.sum()<=600):
        raise ValueError('Invalid ONNX phone duration budget')
    boundaries=np.rint(np.cumsum(durations)/dt+.5).astype(np.int64)
    frames=int(boundaries[-1])
    if not 1<=frames<=52000:raise ValueError('ONNX frame budget exceeded')
    tokens,lang=token_inputs(phone_list,phones,languages,ds.get('lang','en'))
    feed={'tokens':tokens,'languages':lang,'durations':np.diff(boundaries,prepend=0)[None]}
    def curve(name,default=None):
        if name in ds:
            values=np.array([float(x) for x in ds[name].split()],np.float32)
            step=float(ds['f0_timestep' if name=='f0_seq' else name+'_timestep'])
            if not len(values) or not np.isfinite(values).all() or not 0<step<=1:raise ValueError('Invalid ONNX curve')
            return np.interp(np.arange(frames)*dt,np.arange(len(values))*step,values).astype(np.float32)[None]
        if default is None:raise ValueError('ONNX bank requires explicit '+name+' curve/default')
        return np.full((1,frames),default,np.float32)
    feed['f0']=curve('f0_seq')
    for name in ('energy','breathiness','voicing','tension'):
        enabled=config.get('use_'+name+'_embed',False)
        if enabled:feed[name]=curve(name,defaults.get(name+'_db'))
        elif name in ds:raise ValueError('ONNX bank does not support '+name)
    if config.get('use_key_shift_embed'):feed['gender']=curve('gender',defaults.get('gender',0.))
    elif 'gender' in ds:raise ValueError('ONNX bank does not support gender')
    if config.get('use_speed_embed'):feed['velocity']=curve('velocity',defaults.get('speed',1.))
    elif 'velocity' in ds:raise ValueError('ONNX bank does not support speed')
    if type(steps) is not int or not 1<=steps<=100:raise ValueError('Invalid ONNX diffusion steps')
    depth=float(config.get('max_depth',1.))
    if not np.isfinite(depth) or not 0<depth<=1:raise ValueError('Invalid ONNX depth')
    feed.update(depth=np.array(depth,np.float32),steps=np.array(steps,np.int64))
    return feed


def session(path,expected_sha256):
    import onnxruntime as ort
    ort.disable_telemetry_events()
    options=ort.SessionOptions();options.intra_op_num_threads=min(4,os.cpu_count() or 1);options.inter_op_num_threads=1
    # No custom operator libraries or model-provided executable code.
    from app.ai_model_bytes import verified_model_bytes
    data=verified_model_bytes(path,expected_sha256,max_bytes=4*1024**3)
    return ort.InferenceSession(data,sess_options=options,providers=['CPUExecutionProvider'])


def run(request_path,output_path):
    import numpy as np
    import yaml
    import soundfile as sf
    from app.diffsinger_bridge import select_score_phonemes,ds_from_request
    from app.vocal_expression import Expression
    from scipy.signal import resample_poly
    from math import gcd
    value,asset=inventory();bindings=value['bindings']
    for binding,key in (('acoustic','MTA_NEURAL_SINGER_CHECKPOINT'),('vocoder','MTA_DIFFSINGER_VOCODER')):
        if os.getenv(key) and Path(os.environ[key]).resolve()!=asset(bindings[binding]).resolve():
            raise ValueError('ONNX inventory disagrees with selected '+binding)
    if os.getenv('MTA_NEURAL_SINGER_SHA256') and os.environ['MTA_NEURAL_SINGER_SHA256'].lower()!=value['files'][bindings['acoustic']]['sha256']:
        raise ValueError('ONNX acoustic selection checksum mismatch')
    def config(name):
        result=yaml.safe_load(asset_bytes(value,asset,bindings[name],limit=1024**2))
        if not isinstance(result,dict):raise ValueError('Invalid ONNX config')
        return result
    cfg=config('config');vcfg=config('vocoder_config')
    for key in ('sample_rate','hop_size','win_size','fft_size','num_mel_bins','mel_fmin','mel_fmax','mel_base','mel_scale'):
        if key not in cfg or cfg[key]!=vcfg.get(key):raise ValueError('Acoustic/vocoder mismatch: '+key)
    if cfg['sample_rate']!=44100 or cfg['hop_size']!=512 or cfg['num_mel_bins']!=128 or cfg['mel_base']!='e':
        raise ValueError('Unsupported ONNX spectral configuration')
    folder=PurePosixPath(bindings['config']).parent
    acoustic=asset(str(folder/cfg['acoustic']))
    if acoustic!=asset(bindings['acoustic']):raise ValueError('Acoustic binding does not match config')
    if cfg.get('vocoder')!=vcfg.get('name'):raise ValueError('Wrong ONNX vocoder package')
    vocoder=asset(str(PurePosixPath(bindings['vocoder_config']).parent/vcfg['model']))
    if vocoder!=asset(bindings['vocoder']):raise ValueError('Vocoder binding does not match config')
    phones=json.loads(asset_bytes(value,asset,str(folder/cfg['phonemes']),limit=1024**2))
    langs=json.loads(asset_bytes(value,asset,str(folder/cfg['languages']),limit=1024**2))
    path=Path(request_path)
    if path.stat().st_size>1024**2:raise ValueError('Singing request too large')
    request=json.loads(path.read_text())
    if request.get('schema')!='mta-neural-singing-1':raise ValueError('Unsupported ONNX request')
    if request.get('language') not in value['languages']:raise ValueError('ONNX bank does not declare requested language')
    request['expression']=Expression.model_validate({**value.get('expression_defaults',{}),**request.get('expression',{})}).model_dump(exclude_unset=True)
    request=select_score_phonemes(request,lexicon_path=os.getenv('MTA_DIFFSINGER_LEXICON',''),lexicon_sha256=os.getenv('MTA_DIFFSINGER_LEXICON_SHA256',''))
    ds=ds_from_request(request)
    feed=acoustic_inputs(ds,cfg,phones,langs,value.get('expression_defaults',{}),int(os.getenv('MTA_DIFFSINGER_ONNX_STEPS','32')))
    model=session(acoustic,value['files'][bindings['acoustic']]['sha256']);names={i.name for i in model.get_inputs()}
    if names-set(feed):raise ValueError('Unsupported required ONNX inputs: '+str(sorted(names-set(feed))))
    mel=model.run(['mel'],{k:v for k,v in feed.items() if k in names})[0]
    if mel.shape!=(1,feed['f0'].shape[1],128) or not np.isfinite(mel).all():raise ValueError('Invalid inferred mel')
    model=session(vocoder,value['files'][bindings['vocoder']]['sha256'])
    if {i.name for i in model.get_inputs()}!={'mel','f0'}:raise ValueError('Unsupported ONNX vocoder inputs')
    wave=model.run(['waveform'],{'mel':mel,'f0':feed['f0']})[0]
    if wave.ndim!=2 or wave.shape[0]!=1 or not np.isfinite(wave).all() or wave.shape[1]!=mel.shape[1]*512:
        raise ValueError('Invalid ONNX vocoder waveform')
    divisor=gcd(cfg['sample_rate'],48000)
    audio=resample_poly(wave[0],48000//divisor,cfg['sample_rate']//divisor).astype(np.float32)
    peak=float(np.max(np.abs(audio)))
    if peak>.98:audio*=.98/peak
    sf.write(str(output_path),audio,48000,subtype='PCM_24')
    print(json.dumps({'backend':'diffsinger-openutau-onnx','frames':len(audio),'sample_rate':48000,
                      'diffusion_steps':int(feed['steps']),'score_f0':True,'variance_prediction':False,'peak_before_headroom':peak}))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--request',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();run(args.request,args.output)
