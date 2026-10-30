"""CPU adapter for the pinned original-author YourMT3 noPS model.

Runtime source and tensor weights must be installed and integrity-checked by the
operator recipe. This adapter never downloads or unpickles a checkpoint.
"""
import hashlib
import os
from pathlib import Path
import sys

MODEL='yourmt3-nops-5e66c1e'
EXPERIMENT='mc13_256_g4_all_v7_mt3f_sqr_rms_moe_wf4_n8k2_silu_rope_rp_b36_nops'
ARGS=[EXPERIMENT+'@model.safetensors','-p','2024','-tk','mc13_full_plus_256','-dec','multi-t5','-nl','26',
      '-enc','perceiver-tf','-sqr','1','-ff','moe','-wf','4','-nmoe','8','-kmoe','2','-act','silu',
      '-epe','rope','-rp','1','-ac','spec','-hop','300','-atc','1','-pr','32']


def selected_variant():
    variant=os.getenv('MTA_STUDIO_YOURMT3_VARIANT','nops')
    if variant=='nops':return MODEL,EXPERIMENT,'mta-runtime.json'
    if variant=='ps':return 'yourmt3-ps-e45ebd70','mc13_256_g4_all_v7_mt3f_sqr_rms_moe_wf4_n8k2_silu_rope_rp_b80_ps2','mta-runtime-ps.json'
    raise ValueError('Unknown reviewed YourMT3 variant')


def part_identity(drums,program):
    """YourMT3's 100/101 are singing classes, not GM FX programs 100/101."""
    if drums:return 'Drums','drums',None
    if program==100:return 'Singing voice','singing-voice',53
    if program==101:return 'Singing chorus','singing-chorus',52
    return f'GM {program+1}','gm-'+str(program),program


def verified_runtime(*,full=True):
    path=Path(os.environ.get('MTA_STUDIO_YOURMT3_RUNTIME',''))
    if not path.is_absolute() or path.is_symlink():raise ValueError('Configure the installed YourMT3 runtime path')
    model,_,receipt_name=selected_variant()
    receipt=path/receipt_name
    if receipt.is_symlink() or receipt.stat().st_size>131072:raise ValueError('Unsafe YourMT3 runtime receipt')
    from .transcription_source_contract import read_json, verify_sources
    value=read_json(receipt)
    if value.get('model')!=model or value.get('commit')!='5e66c1ea173a8186e0d20432b841d3180cc015b5':raise ValueError('YourMT3 runtime identity mismatch')
    files=value.get('files',{})
    if not isinstance(files,dict) or not 100<=len(files)<=150:raise ValueError('Incomplete YourMT3 runtime manifest')
    verify_sources(path, files, 'yourmt3', model=model)
    for name,digest in files.items():
        target=path/name
        if not isinstance(name,str) or Path(name).is_absolute() or not target.resolve().is_relative_to(path.resolve()) or target.is_symlink():raise ValueError('Unsafe runtime manifest path')
        if full:
            h=hashlib.sha256()
            with target.open('rb') as stream:
                for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
            if h.hexdigest()!=digest:raise ValueError('YourMT3 runtime integrity mismatch: '+name)
    return path


def select_inference_device(torch, requested):
    """Resolve an explicit backend; never silently fall back for a GPU request."""
    if requested == 'cpu':
        return 'cpu'
    if requested not in ('rocm', 'cuda', 'gpu'):
        raise ValueError('MTA_STUDIO_YOURMT3_DEVICE must be cpu, rocm, cuda or gpu')
    if not torch.cuda.is_available():
        raise RuntimeError('YourMT3 GPU requested but PyTorch reports no usable accelerator')
    hip = getattr(torch.version, 'hip', None)
    cuda = getattr(torch.version, 'cuda', None)
    if requested == 'rocm' and not hip:
        raise RuntimeError('YourMT3 ROCm requested but PyTorch is not a HIP build')
    if requested == 'cuda' and (not cuda or hip):
        raise RuntimeError('YourMT3 NVIDIA CUDA requested but PyTorch is not a CUDA build')
    if not (hip or cuda):
        raise RuntimeError('YourMT3 GPU backend identity could not be verified')
    return 'cuda'  # HIP uses the torch.cuda device namespace too.


def transcribe(source,options):
    previous=Path.cwd()
    try:return _transcribe(source,options)
    finally:os.chdir(previous)


def _transcribe(source,options):
    if not isinstance(options,dict) or set(options)-{'name','program'}:
        raise ValueError('YourMT3 accepts name only; isolated-source Basic Pitch thresholds do not apply')
    if 'program' in options:
        raise ValueError('YourMT3 classifies instrument programs; remove the manual program override')
    from .model_license_policy import evaluate_model
    evaluate_model('yourmt3')
    root=verified_runtime()
    from .transcription_source_contract import read_json, imports
    _,_,receipt_name=selected_variant()
    files=read_json(root/receipt_name)['files']
    with imports(root,files,'yourmt3','yourmt3'):
        from .transcription_source_contract import tensor_loader
        with tensor_loader(root,files,'yourmt3',selected_variant()[0]):
            result=_transcribe_verified(source,options,root)
        evaluate_model('yourmt3')
        return result


def _transcribe_verified(source,options,root):
    from .music_interchange import MusicResult,MusicPart
    from .models import MidiNote
    from .ai_studio_adapter import progress
    if set(options)-{'name','program'}:raise ValueError('YourMT3 accepts name only; isolated-source Basic Pitch thresholds do not apply')
    if 'program' in options:raise ValueError('YourMT3 classifies instrument programs; remove the manual program override')
    from .model_license_policy import evaluate_model
    evaluate_model('yourmt3')
    import soundfile as sf
    info=sf.info(str(source))
    if info.channels not in (1,2) or not 0<info.duration<=600 or info.samplerate>192000:raise ValueError('YourMT3 accepts mono/stereo regions up to 10 minutes and 192 kHz')
    model_id,experiment,_=selected_variant()
    os.environ.update({'WANDB_MODE':'disabled','WANDB_SILENT':'true','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1',
                       'HF_HUB_DISABLE_TELEMETRY':'1','OTEL_SDK_DISABLED':'true','DO_NOT_TRACK':'1'})
    # A worker owns one model/runtime and exits after this request.
    sys.path[:0]=[str(root),str(root/'amt/src')]
    os.chdir(root)
    import torch
    import torchaudio
    torch.set_num_threads(min(4,os.cpu_count() or 1))
    from model_helper import load_model_checkpoint,slice_padded_array,merge_zipped_note_events_and_ties_to_notes,mix_notes
    progress('loading-model','Loading verified YourMT3 tensors on CPU')
    arguments=list(ARGS);arguments[0]=experiment+'@model.safetensors'
    device=select_inference_device(torch,os.environ.get('MTA_STUDIO_YOURMT3_DEVICE','cpu'))
    progress('loading-model',f'YourMT3 device: {device}')
    model=load_model_checkpoint(args=arguments,device=device)
    rate=model.audio_cfg['sample_rate'];size=model.audio_cfg['input_frames']
    wave,sr=sf.read(str(source),always_2d=True,dtype='float32')
    audio=torchaudio.functional.resample(torch.from_numpy(wave.mean(axis=1)).reshape(1,-1),sr,rate)
    segments=torch.from_numpy(slice_padded_array(audio,size,size).astype('float32')).unsqueeze(1)
    batches=[]
    with torch.inference_mode():
        for index in range(len(segments)):
            progress('transcribing',f'YourMT3 audio window {index+1}/{len(segments)}; decoding time varies')
            inputs=segments[index:index+1].to(device)
            from .model_license_policy import guarded_model_call
            tokens,_=guarded_model_call('yourmt3',model.inference_file,bsz=1,audio_segments=inputs);batches.extend(tokens)
    starts=[size*i/rate for i in range(len(segments))];voices=[]
    for channel in range(model.task_manager.num_decoding_channels):
        sequence=[arr[:,channel,:] for arr in batches]
        zipped,_,_=model.task_manager.detokenize_list_batches(sequence,starts,return_events=True)
        notes,_=merge_zipped_note_events_and_ties_to_notes(zipped);voices.append(notes)
    groups={}
    note_index=0
    from .transcription_timing import bound_interval
    trimmed=dropped=0
    for event in mix_notes(voices):
        interval=bound_interval(float(event.onset),float(event.offset),info.duration)
        if interval is None:
            dropped+=1;continue
        start,end=interval
        trimmed+=interval!=(event.onset,event.offset)
        key=(bool(event.is_drum),0 if event.is_drum else int(event.program))
        groups.setdefault(key,[]).append(MidiNote(id=f'ym-{note_index}',pitch=int(event.pitch),
            start_ms=start*1000,duration_ms=(end-start)*1000,
            velocity=96,channel=9 if event.is_drum else 0,origin='predicted',source_model=model_id))
        note_index+=1
        if note_index>75000:raise ValueError('YourMT3 output exceeds musical event budget')
    if not groups:
        from .music_interchange import no_notes
        return no_notes(['YourMT3 detected no notes in this region; no tracks were invented.'])
    parts=[];melodic=0
    channels=[c for c in range(16) if c!=9]
    for i,((drums,program),notes) in enumerate(sorted(groups.items())):
        channel=9 if drums else channels[melodic%len(channels)]
        if not drums:melodic+=1
        name,instrument,playback_program=part_identity(drums,program)
        parts.append(MusicPart(id=f'part-{i}',name=name,program=playback_program,
            percussion=drums,instrument=instrument,
            notes=[note.model_copy(update={'channel':channel}) for note in notes],source_model=model_id))
    return MusicResult(parts=parts,warnings=[
        'Instrument labels, pitch and timing are model predictions and require review.',
        f'Source audio bounds: {trimmed} note intervals trimmed; {dropped} invalid/padding intervals discarded.',
        'Velocity 96 is generated; this model checkpoint does not estimate playing dynamics.',
        'Programs are model-class representatives. Singing classes 100/101 use generated GM playback programs 53/52, not inferred FX timbres.',
        'Calibrated confidence, pitch bend, controllers and independent players of the same instrument are unavailable.',
        'More than 15 melodic parts share MIDI channels; use per-track instruments or remap channels before hardware/SMF playback.' if melodic>15 else 'Melodic parts use distinct MIDI channels; percussion uses channel 10.',
        'GPU execution requires independent hardware validation; broad mixed-instrument accuracy is not certified.'])
