"""Leave headroom for resampling Seed's bounded BigVGAN output.

This does not undo BigVGAN's own output clamp or certify timbre quality.
"""


def with_headroom(audio,sample_rate=48000):
    import torch
    if (not isinstance(audio,torch.Tensor) or not audio.is_floating_point()
            or audio.ndim!=2 or not audio.numel() or not torch.isfinite(audio).all()):
        raise ValueError('Seed generated invalid audio')
    peak=float(audio.abs().max())
    if sample_rate!=48000:
        from math import gcd
        import numpy as np
        from scipy.signal import resample_poly
        divisor=gcd(sample_rate,48000)
        # Same filter and float32 precision as vocal_conversion.convert.
        projected=resample_poly(audio.detach().cpu().numpy(),48000//divisor,
                                sample_rate//divisor,axis=-1)
        peak=max(peak,float(np.max(np.abs(projected))))
    gain=min(1.,.98/peak) if peak else 1.
    return audio*gain,gain


def install_export_guard():
    import torchaudio
    save=torchaudio.save

    def export(path,audio,sample_rate,*args,**kwargs):
        audio,gain=with_headroom(audio,sample_rate)
        print('Seed PCM export linear headroom gain:',gain,flush=True)
        return save(path,audio,sample_rate,*args,**kwargs)

    torchaudio.save=export
