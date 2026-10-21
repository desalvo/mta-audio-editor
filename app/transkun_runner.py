"""Transkun model API runner; bypasses upstream CLI's MP3-only input loader.

Invoked only from the admitted worker with hash-verified administrator assets.
Never exposed as a filesystem-path API. The upstream configuration is executable
Python/moduleconf and the trusted checkpoint can contain pickle metadata.
"""
import argparse
import sys
from pathlib import Path


def main():
    parser=argparse.ArgumentParser()
    for key in ('source','output','checkpoint','config','runtime','device'):parser.add_argument('--'+key,required=True)
    args=parser.parse_args()
    from studio_offline_runner import activate
    activate()
    sys.path.insert(0,str(Path(args.runtime).resolve()))
    import numpy as np
    import soundfile as sf
    import torch
    import moduleconf
    from transkun.Data import writeMidi
    settings=moduleconf.parseFromFile(args.config)
    model=settings['Model'].module.TransKun(conf=settings['Model'].config).to(args.device)
    checkpoint=torch.load(args.checkpoint,map_location=args.device,weights_only=False)
    state=checkpoint.get('best_state_dict',checkpoint.get('state_dict'))
    if not isinstance(state,dict):raise ValueError('Transkun checkpoint has no model weights')
    # Upstream uses strict=False. Reject missing/unexpected tensors here instead
    # of silently using uninitialized weights under a new upstream architecture.
    model.load_state_dict(state,strict=True);model.eval()
    # Upstream enables training gradient checkpointing even in eval mode.
    # Inference has no autograd graph; bypass this path rather than depending
    # on PyTorch's changing checkpoint(use_reentrant=...) defaults.
    for layer in model.modules():
        if hasattr(layer,'useGradientCheckpoint'):
            layer.useGradientCheckpoint=False
    audio,rate=sf.read(args.source,dtype='float32',always_2d=True)
    if not len(audio) or not np.isfinite(audio).all():raise ValueError('Invalid piano source PCM')
    if rate!=model.fs:
        import soxr
        audio=soxr.resample(audio,rate,model.fs)
    with torch.inference_mode():
        notes=model.transcribe(torch.from_numpy(np.asarray(audio,dtype='float32')).to(args.device),
                               stepInSecond=None,segmentSizeInSecond=None,discardSecondHalf=False)
    writeMidi(notes).write(args.output)

if __name__=='__main__':main()
