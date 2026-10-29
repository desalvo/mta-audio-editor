"""Model-specific Seed-VC/RVC offline conversion; no pitch-shifter substitutes."""
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Annotated
from pydantic import BaseModel,ConfigDict,Field


class ConversionSettings(BaseModel):
    model_config=ConfigDict(extra='forbid')
    asset_id:Annotated[str,Field(pattern=r'^$|^[a-z][a-z0-9-]{0,63}$')]=''
    mix:float=Field(default=1.,ge=0,le=1,allow_inf_nan=False)
    diffusion_steps:int=Field(default=30,ge=1,le=200)
    guidance:float=Field(default=.7,ge=0,le=1,allow_inf_nan=False)
    pitch_semitones:int=Field(default=0,ge=-24,le=24)
    speaker_id:int=Field(default=0,ge=0,le=10000)
    index_rate:float=Field(default=.75,ge=0,le=1,allow_inf_nan=False)
    protect:float=Field(default=.33,ge=0,le=.5,allow_inf_nan=False)


def command(value,python,source,output,cfg):
    """Arguments verified against the upstream model-specific CLIs."""
    from .studio_asset_registry import binding
    kind=value['kind'];script=binding(value,'script')
    runner='seed_vc_runner.py' if kind=='seed-vc' else 'studio_offline_runner.py'
    prefix=[str(python),str(Path(__file__).with_name(runner)),str(script)]
    if kind=='seed-vc':
        validate_seed_config(binding(value,'config'))
        return [*prefix,'--source',str(source),'--target',str(binding(value,'reference')),
                '--output',str(output),'--checkpoint',str(binding(value,'checkpoint')),'--config',str(binding(value,'config')),
                '--diffusion-steps',str(cfg.diffusion_steps),'--length-adjust','1.0',
                '--inference-cfg-rate',str(cfg.guidance),'--f0-condition','True','--auto-f0-adjust','False',
                '--semi-tone-shift',str(cfg.pitch_semitones),'--fp16','False']
    if kind=='rvc':
        args=[*prefix,'--model',str(binding(value,'checkpoint')),'--input',str(source),
              '--output',str(output/'converted.wav'),'--speaker-id',str(cfg.speaker_id),
              '--pitch',str(cfg.pitch_semitones),'--f0-method','rmvpe','--format','wav',
              '--index-rate',str(cfg.index_rate),'--protect',str(cfg.protect),'--rms-mix-rate','1.0']
        if 'index' in value['bindings']:args+=['--index',str(binding(value,'index'))]
        elif cfg.index_rate:raise ValueError('RVC retrieval needs an installed pinned index; set index rate to zero for no retrieval')
        return args
    raise ValueError('Selected bundle is not a Seed-VC/RVC conversion model')


def validate_seed_config(path):
    """Singing conversion requires the 44.1 kHz F0-conditioned architecture.

    The speech checkpoint uses 22.05 kHz and different Whisper dimensions;
    passing --f0-condition True cannot turn it into the singing model.
    """
    import yaml
    path=Path(path)
    if path.stat().st_size>1024*1024:
        raise ValueError('Seed-VC configuration is too large')
    config=yaml.safe_load(path.read_text(encoding='utf-8'))
    try:
        params=config['model_params']
        compatible=(config['preprocess_params']['sr']==44100
                    and params['DiT']['f0_condition'] is True
                    and params['length_regulator']['f0_condition'] is True)
    except (KeyError,TypeError):
        compatible=False
    if not compatible:
        raise ValueError('Seed-VC singing requires a matching 44.1 kHz F0-conditioned config and checkpoint; speech weights are incompatible')


def _check_pcm(samples, label):
    """Reject invalid audio after each transform, before source replacement."""
    import numpy as np
    if (not isinstance(samples, np.ndarray) or samples.size == 0
            or samples.ndim not in (1, 2) or not np.issubdtype(samples.dtype, np.floating)
            or not np.isfinite(samples).all() or np.max(np.abs(samples)) > 1.0):
        raise ValueError(f'{label} contains invalid or clipped PCM')


def convert(path,settings,progress=lambda *a:None):
    from .studio_asset_registry import runtime,binding
    import numpy as np
    import soundfile as sf
    cfg=ConversionSettings.model_validate(settings)
    if not cfg.asset_id:return None
    value,python=runtime(cfg.asset_id)
    if value['kind'] not in ('seed-vc','rvc'):raise ValueError('Select a real Seed-VC/RVC bundle')
    source=Path(path).resolve(strict=True)
    info=sf.info(source)
    if info.channels!=1 or info.samplerate!=48000 or not 0<info.duration<=610:raise ValueError('Invalid conversion source')
    # All HF auxiliary models must already be present in the pinned local cache.
    env={**os.environ,'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','HF_HUB_DISABLE_TELEMETRY':'1',
         'WANDB_MODE':'disabled','PYTHONDONTWRITEBYTECODE':'1','DO_NOT_TRACK':'1',
         'MTA_STUDIO_OFFLINE_KIND':value['kind'],'MTA_STUDIO_CONVERSION_ASSET_ID':cfg.asset_id}
    if 'hf_home' in value['bindings']:env['HF_HOME']=str(binding(value,'hf_home'))
    progress('voice-conversion',value['name'])
    with tempfile.TemporaryDirectory(prefix='.conversion-',dir=source.parent) as temporary:
        output=Path(temporary)
        subprocess.run(command(value,python,source,output,cfg),cwd=binding(value,'runtime_root'),env=env,
                       stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                       timeout=600,check=True)
        files=list(output.glob('*.wav'))
        if len(files)!=1 or files[0].is_symlink() or not files[0].is_file() or files[0].stat().st_nlink!=1:
            raise ValueError('Conversion must produce exactly one private WAV')
        converted_info=sf.info(files[0])
        if (not 8000<=converted_info.samplerate<=192000 or converted_info.channels not in (1,2)
                or abs(converted_info.duration-info.duration)>.25):
            raise ValueError('Converted audio duration/format would break score synchronization')
        audio,rate=sf.read(files[0],dtype='float32',always_2d=True);audio=audio.mean(axis=1)
        if not len(audio) or not np.isfinite(audio).all() or np.max(abs(audio))>1.01:raise ValueError('Invalid/clipped conversion output')
        if rate!=48000:
            from scipy.signal import resample_poly
            from math import gcd
            d=gcd(rate,48000);audio=resample_poly(audio,48000//d,rate//d).astype('float32')
        # Resampling may overshoot even when source samples are bounded.
        # Validate the actual signal which will be saved, including the dry
        # stream, before replacing the source atomically.
        _check_pcm(audio, 'Resampled conversion output')
        dry,_=sf.read(source,dtype='float32')
        _check_pcm(dry, 'Conversion source')
        aligned=np.zeros(len(dry),dtype='float32');aligned[:min(len(aligned),len(audio))]=audio[:len(aligned)]
        mixed=dry*(1-cfg.mix)+aligned*cfg.mix
        _check_pcm(mixed, 'Converted blend')
        final=output/'aligned.wav';sf.write(final,mixed,48000,subtype='PCM_24')
        os.replace(final,source)
    return {'asset_id':cfg.asset_id,'backend':value['kind'],'settings':cfg.model_dump(),
            'checkpoint_sha256':value['files'][value['bindings']['checkpoint']]['sha256'],
            'reference_duration_alignment':'trim/pad at most 250 ms; no time-stretching',
            'seed_export_peak_ceiling':.98 if value['kind']=='seed-vc' else None,
            'inference_process_completed':True,'musical_quality_validated':False}
