"""Use the selected MDX checkpoint on ROCm through PyTorch, not CPU-only ORT."""
import logging
from pathlib import Path
import shutil

_LOG = logging.getLogger(__name__)


def split_center_side(source, output_dir, *, cancel_event=None):
    """Explicit DSP route shared by desktop and the registered server worker."""
    from .model_license_policy import evaluate_model
    from .separator_process import run
    evaluate_model('mta-analysis')
    if shutil.which('ffmpeg') is None:
        raise RuntimeError('FFmpeg is required for lead/backing vocal fallback separation')
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    lead, backing = output_dir / 'lead_vocals.wav', output_dir / 'backing_vocals.wav'
    filters = ('[0:a]asplit=2[a][b];'
               '[a]pan=stereo|c0=0.5*c0+0.5*c1|c1=0.5*c0+0.5*c1[lead];'
               '[b]pan=stereo|c0=0.5*c0-0.5*c1|c1=0.5*c1-0.5*c0[backing]')
    run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', str(source),
         '-filter_complex', filters, '-map', '[lead]', '-c:a', 'pcm_s24le', str(lead),
         '-map', '[backing]', '-c:a', 'pcm_s24le', str(backing)], cancel_event=cancel_event, own_session=False)
    return lead, backing, 'ffmpeg-center-side'


def backing_policy(model_filename):
    """Resolve only the shipped separator selectors, never a caller's policy ID."""
    from .ai_backend_models import LEAD_BACKING_MODELS
    from .model_license_policy import evaluate_model
    models = {m['filename']: m['id'] for m in LEAD_BACKING_MODELS if m['id'] != 'mvsep-mega53'}
    if not isinstance(model_filename, str) or model_filename not in models:
        raise ValueError('Unsupported backing-vocal checkpoint filename')
    model = models[model_filename]
    return evaluate_model('uvr-kara-2' if model == 'uvr_mdxnet_kara_2' else 'audio-separator-weights')


def separate_backing(separator, source, model_filename):
    """A loaded separator cannot retain a permission revoked after loading."""
    backing_policy(model_filename)
    if getattr(separator, '_mta_backing_filename', None) != model_filename:
        raise ValueError('Backing-vocal separator does not match the admitted checkpoint')
    outputs = separator.separate(str(source))
    backing_policy(model_filename)
    return outputs


def load_backing_model(separator, model_filename):
    backing_policy(model_filename)
    # A failed/revoked reload must not leave a previous load usable through MTA.
    separator._mta_backing_filename = None
    separator.load_model(model_filename=model_filename)
    backing_policy(model_filename)
    if Path(model_filename).suffix.lower() != '.onnx':
        separator._mta_backing_filename = model_filename
        return
    import torch
    if not getattr(getattr(torch, 'version', None), 'hip', None) or not torch.cuda.is_available():
        separator._mta_backing_filename = model_filename
        return
    instance = getattr(separator, 'model_instance', None)
    if instance is None or not hasattr(instance, 'model_run') or not getattr(instance, 'model_path', None):
        raise RuntimeError('MTA_BACKING_FAILURE:unsupported_mdx_runtime')
    try:
        from onnx2torch import convert
        # Keep the selected checkpoint and its original segment dimensions.
        # Upstream already supports this conversion for MDX; selecting a smaller
        # segment just to trigger its conversion would change inference windows.
        device = torch.device('cuda')  # PyTorch's ROCm device API.
        model = convert(str(instance.model_path)).to(device).eval()

        def run(spectrum):
            backing_policy(model_filename)
            with torch.inference_mode():
                result = model(spectrum.to(device))
            return result.detach().cpu().numpy()

        instance.model_run = run
        instance.torch_device = device
        instance.uses_pytorch_inference = True
        # Keep a strong reference and expose the actual execution route locally.
        instance.mta_rocm_model = model
        instance.mta_execution_backend = 'pytorch-rocm'
        separator._mta_backing_filename = model_filename
        _LOG.info('Backing-vocal MDX inference configured for PyTorch ROCm')
    except Exception as exc:
        # Do not silently run a GPU-selected job on CPU or change its model.
        raise RuntimeError('MTA_BACKING_FAILURE:rocm_conversion_failed') from exc
