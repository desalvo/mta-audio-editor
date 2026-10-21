"""Two reviewed YourMT3 checkpoints to tensor-only conversion.

Never import checkpoint model classes or use weights_only=False. This utility
accepts only the original author's pinned noPS/PS artifacts, not user checkpoints.
"""
import hashlib
from pathlib import Path

SHA256='ae38e415c79efd5592dcb9b658cdb99ddb11d4c4e1eaa364cab04a052473fc25'
SIZE=561544628
PS_SHA256='7427055b51c3c8c86f6a35493cf0741d8db29186052055b59193590a82e6ec01'
PS_SIZE=758957292


class DiscardedMetadata:
    def __new__(cls,*args,**kwargs):return object.__new__(cls)
    def __setstate__(self,state):pass


def convert(source,output,variant='nops'):
    source=Path(source);output=Path(output)
    if variant not in ('nops','ps'):raise ValueError('Unknown reviewed YourMT3 variant')
    size,digest_expected=(SIZE,SHA256) if variant=='nops' else (PS_SIZE,PS_SHA256)
    if source.is_symlink() or source.stat().st_size!=size:raise ValueError('Unexpected checkpoint size or file')
    digest=hashlib.sha256()
    with source.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    if digest.hexdigest()!=digest_expected:raise ValueError('Checkpoint digest mismatch')
    import torch
    import numpy as np
    from safetensors.torch import save_file
    names=('utils.task_manager.TaskManager','utils.event_codec.FastCodec','utils.tokenizer.NoteEventTokenizer',
           'utils.note_event_dataclasses.EventRange','utils.note_event_dataclasses.Event')
    allowed=[(DiscardedMetadata,name) for name in names]+[np.core.multiarray.scalar,np.core.multiarray._reconstruct,np.dtype,np.ndarray]
    allowed += [type(np.dtype(t)) for t in ('float32','float64','int32','int64','uint8','bool','U1')]
    with torch.serialization.safe_globals(allowed):checkpoint=torch.load(source,map_location='cpu',weights_only=True)
    state=checkpoint.get('state_dict')
    if not isinstance(state,dict):raise ValueError('Checkpoint has no tensor dictionary')
    state={k:v for k,v in state.items() if isinstance(k,str) and 'pitchshift' not in k}
    if len(state)!=655 or any(not isinstance(v,torch.Tensor) or v.layout!=torch.strided or v.dtype not in (torch.float32,torch.int64) for v in state.values()):
        raise ValueError('Unexpected checkpoint tensor types')
    if sum(v.dtype==torch.int64 for v in state.values())!=6 or any(v.dtype==torch.int64 and (v.ndim!=0 or not k.endswith('.num_batches_tracked')) for k,v in state.items()):raise ValueError('Unexpected integer tensors')
    if sum(v.numel() for v in state.values())!=47081642:raise ValueError('Unexpected checkpoint tensor budget')
    if output.exists() or output.is_symlink():raise ValueError('Tensor output already exists')
    save_file({k:v.clone().contiguous() for k,v in state.items()},str(output),metadata={'source_sha256':digest_expected})
    return {'tensors':len(state),'elements':47081642,'sha256':hashlib.sha256(output.read_bytes()).hexdigest()}
