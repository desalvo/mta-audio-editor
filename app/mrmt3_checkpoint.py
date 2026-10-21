"""Tensor-only conversion of the exact original MR-MT3-family public artifact."""
import hashlib
from pathlib import Path
import os
import tempfile

RAW_SHA='b8a3807ed265059abd25ad7f68142c06c35e8f6144dcaa45bd55946a3745398f'
RAW_SIZE=183672643


def convert(source,output):
    source=Path(source);output=Path(output)
    if source.is_symlink() or not source.is_file() or source.stat().st_size!=RAW_SIZE:
        raise ValueError('MR-MT3 checkpoint size mismatch')
    with source.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    if digest!=RAW_SHA:raise ValueError('MR-MT3 checkpoint SHA-256 mismatch')
    if output.exists():raise ValueError('Choose a new MR-MT3 tensor destination')
    import torch
    from safetensors.torch import save_file
    value=torch.load(source,map_location='cpu',weights_only=True)
    if (not isinstance(value,dict) or len(value)!=193 or
            any(not isinstance(k,str) or not isinstance(v,torch.Tensor) or v.dtype!=torch.float32 for k,v in value.items()) or
            sum(v.numel() for v in value.values())!=46945792 or
            any(not torch.isfinite(v).all() for v in value.values())):
        raise ValueError('MR-MT3 tensor structure mismatch')
    fd,tmp=tempfile.mkstemp(prefix='.mrmt3-',dir=output.parent);os.close(fd)
    try:
        save_file({k:v.detach().cpu().contiguous().clone() for k,v in value.items()},tmp)
        os.link(tmp,output)
    finally:Path(tmp).unlink(missing_ok=True)
    return {'source_sha256':digest,'tensors':193,'elements':46945792,
            'sha256':hashlib.file_digest(output.open('rb'),'sha256').hexdigest(),'bytes':output.stat().st_size}


if __name__=='__main__':
    import argparse,json
    parser=argparse.ArgumentParser();parser.add_argument('source');parser.add_argument('output')
    args=parser.parse_args();print(json.dumps(convert(args.source,args.output)))
