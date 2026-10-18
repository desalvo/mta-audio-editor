"""Use the selected MDX checkpoint on ROCm through PyTorch, not CPU-only ORT."""
import logging
from pathlib import Path

_LOG = logging.getLogger(__name__)


def load_backing_model(separator, model_filename):
    separator.load_model(model_filename=model_filename)
    if Path(model_filename).suffix.lower() != '.onnx':
        return
    import torch
    if not getattr(getattr(torch, 'version', None), 'hip', None) or not torch.cuda.is_available():
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
            with torch.inference_mode():
                result = model(spectrum.to(device))
            return result.detach().cpu().numpy()

        instance.model_run = run
        instance.torch_device = device
        instance.uses_pytorch_inference = True
        # Keep a strong reference and expose the actual execution route locally.
        instance.mta_rocm_model = model
        instance.mta_execution_backend = 'pytorch-rocm'
        _LOG.info('Backing-vocal MDX inference configured for PyTorch ROCm')
    except Exception as exc:
        # Do not silently run a GPU-selected job on CPU or change its model.
        raise RuntimeError('MTA_BACKING_FAILURE:rocm_conversion_failed') from exc
