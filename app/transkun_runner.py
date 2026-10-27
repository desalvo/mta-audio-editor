"""Transkun model API runner; bypasses upstream CLI's MP3-only input loader.

Invoked only from the admitted worker with hash-verified administrator assets.
Never exposed as a filesystem-path API. The upstream configuration is executable
Python/moduleconf but checkpoint loading accepts only the weights-only PyTorch format.
Unsupported legacy metadata fails closed; no unrestricted pickle fallback exists.
"""
import argparse
import io
import tempfile
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from app.ai_model_bytes import verified_model_bytes


def load_state(torch,checkpoint_path,device,expected_sha256):
    """No unsafe retry, allowlist expansion or executable checkpoint metadata."""
    data=verified_model_bytes(checkpoint_path,expected_sha256,max_bytes=4*1024**3)
    with io.BytesIO(data) as stream:
        checkpoint=torch.load(stream,map_location=device,weights_only=True)
    if not isinstance(checkpoint,dict):raise ValueError('Transkun checkpoint must be a tensor dictionary')
    state=checkpoint.get('best_state_dict',checkpoint.get('state_dict'))
    if not isinstance(state,dict) or not state or any(not isinstance(k,str) or not isinstance(v,torch.Tensor) for k,v in state.items()):
        raise ValueError('Transkun checkpoint has no safe model weights')
    return state


def load_settings(moduleconf,config_path,expected_sha256):
    """Give moduleconf a private copy of the exact verified config bytes.

    Configuration is still trusted executable operator code, not sandboxed.
    """
    data=verified_model_bytes(config_path,expected_sha256,max_bytes=1024**2)
    with tempfile.TemporaryDirectory(prefix='mta-transkun-config-') as folder:
        path=Path(folder)/Path(config_path).name
        path.write_bytes(data);path.chmod(0o400)
        return moduleconf.parseFromFile(str(path))


def main():
    parser=argparse.ArgumentParser()
    for key in ('source','output','checkpoint','checkpoint-sha256','config','config-sha256','runtime','device'):parser.add_argument('--'+key,required=True)
    args=parser.parse_args()
    from studio_offline_runner import activate
    activate()
    sys.path.insert(0,str(Path(args.runtime).resolve()))
    import numpy as np
    import soundfile as sf
    import torch
    import moduleconf
    from transkun.Data import writeMidi
    settings=load_settings(moduleconf,args.config,args.config_sha256)
    model=settings['Model'].module.TransKun(conf=settings['Model'].config).to(args.device)
    state=load_state(torch,args.checkpoint,args.device,args.checkpoint_sha256)
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
