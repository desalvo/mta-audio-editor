"""Pinned optional MR-MT3-family inference; never downloads or unpickles weights."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys

MODEL='mr-mt3-b8a3807e'
SOURCE_COMMIT='d8cbd287470291dee335f84315c5a9b9ff6e6c8a'
WEIGHTS='weights/model.safetensors'
REQUIRED={WEIGHTS,*('source/mt3_infer/'+name for name in (
    '__init__.py','base.py','exceptions.py','adapters/__init__.py','adapters/mr_mt3.py',
    'adapters/vocab_utils.py','models/__init__.py','models/mr_mt3/__init__.py','models/mr_mt3/t5.py'))}


def _sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def verified_runtime(full=True,require_tested=True):
    root=Path(os.getenv('MTA_STUDIO_MRMT3_RUNTIME',''))
    if not root.is_absolute() or root.is_symlink():raise ValueError('Configure the reviewed MR-MT3 runtime')
    receipt=root/'mta-runtime.json'
    if receipt.is_symlink() or not receipt.is_file() or receipt.stat().st_size>65536:
        raise ValueError('Missing/unsafe MR-MT3 receipt')
    value=json.loads(receipt.read_text())
    if (value.get('schema')!='mta-mrmt3-runtime-1' or value.get('model')!=MODEL or
            value.get('source_commit')!=SOURCE_COMMIT or (require_tested and value.get('tested') is not True)):
        raise ValueError('Unverified MR-MT3 runtime identity')
    files=value.get('files')
    if not isinstance(files,dict) or not 10<=len(files)<=32 or not REQUIRED<=set(files):
        raise ValueError('Incomplete MR-MT3 inventory')
    for name,digest in files.items():
        if (not isinstance(name,str) or '\\' in name or PurePosixPath(name).is_absolute() or
                any(x in ('','..','.') for x in name.split('/')) or not isinstance(digest,str) or not re.fullmatch('[a-f0-9]{64}',digest)):
            raise ValueError('Unsafe MR-MT3 inventory')
        target=root/name
        if target.is_symlink() or not target.is_file() or not target.resolve().is_relative_to(root.resolve()):
            raise ValueError('Unsafe/missing MR-MT3 runtime file')
        if full and _sha(target)!=digest:raise ValueError('MR-MT3 runtime integrity mismatch: '+name)
    python=root/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if python.is_symlink() or not python.is_file() or _sha(python)!=value.get('python_sha256'):
        raise ValueError('MR-MT3 interpreter integrity mismatch; use a venv created with --copies')
    return root,value,python


def python_for():
    try:return verified_runtime(full=False)[2]
    except (ValueError,OSError,KeyError):return None


def transcribe(source,options):
    return _transcribe(source,options)


def _transcribe(source,options,*,_require_tested=True):
    from .music_interchange import MusicPart,MusicResult,no_notes
    from .models import MidiNote
    from .ai_studio_adapter import progress
    from .music_channels import route_parts
    from .mrmt3_decode import decode
    if not isinstance(options,dict) or set(options)-{'name'}:
        raise ValueError('MR-MT3 classifies programs; only the source name is configurable')
    name=options.get('name','Transcribed mix')
    if not isinstance(name,str) or not 1<=len(name)<=180:raise ValueError('Invalid MR-MT3 source name')
    import soundfile as sf
    import numpy as np
    from scipy.signal import resample_poly
    from math import gcd
    info=sf.info(str(source))
    if info.channels not in (1,2) or not 8000<=info.samplerate<=192000 or not 0<info.duration<=600:
        raise ValueError('MR-MT3 accepts mono/stereo audio up to 600 seconds and 192 kHz')
    root,_,_=verified_runtime(require_tested=_require_tested)
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',DO_NOT_TRACK='1')
    sys.path.insert(0,str(root/'source'))
    import torch
    import transformers
    from safetensors.torch import load_file
    if transformers.__version__!='5.13.1':raise ValueError('MR-MT3 requires its reviewed Transformers 5.13.1 runtime')
    from transformers import T5Config
    from mt3_infer.adapters.mr_mt3 import MRMT3Adapter,_import_t5_model
    torch.set_num_threads(min(4,os.cpu_count() or 1))
    progress('loading-model','Loading verified MR-MT3-family tensors on CPU')
    adapter=MRMT3Adapter()
    adapter.model=_import_t5_model()(T5Config.from_dict(adapter.model_config))
    # The upstream convenience loader uses unrestricted pickle/partial loading.
    # This path only reads safetensors and requires every architecture tensor.
    adapter.model.load_state_dict(load_file(str(root/WEIGHTS),device='cpu'),strict=True)
    adapter.model.eval();adapter._initialize_vocab();adapter._model_loaded=True
    wave,rate=sf.read(str(source),always_2d=True,dtype='float32')
    if not np.isfinite(wave).all():raise ValueError('Non-finite source audio')
    factor=gcd(rate,16000);wave=resample_poly(wave.mean(axis=1),16000//factor,rate//factor).astype('float32')
    # Preserve the last partial hop instead of dropping source samples.
    padding=(-len(wave))%128
    if padding:wave=np.pad(wave,(0,padding))
    features=adapter.preprocess(wave,16000)
    predictions=[]
    with torch.inference_mode():
        for index in range(len(features['inputs'])):
            progress('transcribing',f'MR-MT3 window {index+1}/{len(features["inputs"])}')
            selected={key:value[index:index+1] for key,value in features.items()}
            output=adapter.forward(selected)
            tokens=output['tokens'][0];tokens=tokens[tokens>=0]
            predictions.append({'est_tokens':tokens,'start_time':float(output['frame_times'][0][0])})
    notes,audit=decode(predictions,adapter.codec,info.duration)
    if not notes:return no_notes(['MR-MT3 detected no notes; no substitute parts generated.'])
    groups={}
    for note in notes:groups.setdefault((note['is_drum'],note['program']),[]).append(note)
    parts=[]
    for index,((drums,program),events) in enumerate(sorted(groups.items())):
        parts.append(MusicPart(id=f'mr-{index}',name=(name+(' / Drums' if drums else f' / GM {program+1}'))[:200],
            program=None if drums else program,instrument='drums' if drums else f'gm-{program}',percussion=drums,
            source_model=MODEL,notes=[MidiNote(id=f'mr-{index}-{j}',pitch=n['pitch'],start_ms=n['start_time']*1000,
                duration_ms=(n['end_time']-n['start_time'])*1000,velocity=n['velocity'],origin='predicted',source_model=MODEL)
                for j,n in enumerate(events)]))
    parts,routing=route_parts(parts)
    return MusicResult(parts=parts,warnings=[
        'Original MR-MT3-family mt3.pth checkpoint; not a guarantee of 10–16 correctly identified instruments.',
        'Velocity is generated from one nonzero model bin; drum duration 10 ms is generated; no calibrated confidence.',
        'GM identity is retained directly from model tokens; the upstream single-channel MIDI wrapper is not used.',
        f'Decoder audit: {audit["invalid_events"]} invalid events, {audit["dropped_events"]} beyond-window events, {audit["unclosed_notes"]} open notes closed at last decoded time.',
        *routing])
