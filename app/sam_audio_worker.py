"""Opt-in SAM Audio CLI worker. Requires authorized Hugging Face access.

Install from https://github.com/facebookresearch/sam-audio in a separate venv.
No checkpoints are shipped with MTA Audio Editor.
"""
import argparse
import json
import sys
from pathlib import Path


def _failure_reason(error):
    """Return only fixed diagnostic codes; never expose exception messages."""
    seen = set()
    for _ in range(8):
        if error is None or id(error) in seen:
            break
        seen.add(id(error))
        name = type(error).__name__
        if name in {'OutOfMemoryError', 'MemoryError'}:
            return 'insufficient_memory'
        if name == 'RuntimeError' and 'out of memory' in str(error).lower():
            return 'insufficient_memory'
        if name in {'GatedRepoError', 'HfHubHTTPError', 'HTTPError', 'HTTPStatusError'}:
            status = getattr(getattr(error, 'response', None), 'status_code', None)
            if name == 'GatedRepoError' or status in (401, 403):
                return 'checkpoint_access_denied'
            if status == 404:
                return 'checkpoint_not_found_or_inaccessible'
            if status == 429:
                return 'hub_rate_limited'
        if name in {'RepositoryNotFoundError', 'RevisionNotFoundError', 'EntryNotFoundError'}:
            return 'checkpoint_not_found_or_inaccessible'
        if name in {'LocalEntryNotFoundError', 'OfflineModeIsEnabled', 'ConnectionError',
                    'ConnectTimeout', 'ReadTimeout', 'TimeoutError', 'SSLError'}:
            return 'hub_unavailable_or_cache_missing'
        if name in {'SafetensorError', 'UnpicklingError'}:
            return 'checkpoint_format_invalid'
        error = error.__cause__ or error.__context__
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--anchors-json", default="")
    args = parser.parse_args()
    # Also enforce policy when called without the unified parent/registry.
    if __package__ in (None, ''):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.model_license_policy import evaluate_model
    evaluate_model('sam-audio')
    from app.model_selectors import sam_model
    args.model = sam_model(args.model)
    stage = "imports"
    try:
        import torch
        import torchaudio
        from sam_audio import SAMAudio, SAMAudioProcessor
        device = "cuda" if torch.cuda.is_available() else "cpu"
        from app.sam_audio_compat import sam_hub_compat
        stage = "model_load"
        with sam_hub_compat():
            model = SAMAudio.from_pretrained(args.model).eval()
        stage = "device_transfer"
        model = model.to(device)
        stage = "processor_load"
        processor = SAMAudioProcessor.from_pretrained(args.model)
        prompt_args = {"audios": [args.source], "descriptions": [args.prompt]}
        if args.anchors_json:
            anchors = json.loads(args.anchors_json)
            if not isinstance(anchors, list) or not anchors or any(not isinstance(anchor, list) or len(anchor) != 3 or anchor[0] not in {"+", "-"} for anchor in anchors):
                raise ValueError("Invalid SAM Audio temporal anchors")
            prompt_args["anchors"] = [anchors]
        stage = "audio_processing"
        inputs = processor(**prompt_args).to(device)
        stage = "inference"
        with torch.inference_mode():
            result = model.separate(inputs, predict_spans=False, reranking_candidates=1)
        stage = "audio_save"
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        audio = result.target.detach().cpu()
        if audio.ndim == 3 and audio.shape[0] == 1:
            audio = audio[0]
        torchaudio.save(str(path), audio, processor.audio_sampling_rate)
    except Exception as exc:
        reason = _failure_reason(exc)
        if reason:
            print("MTA_SAM_REASON:" + reason, file=sys.stderr, flush=True)
        print("MTA_SAM_FAILURE:" + stage, file=sys.stderr, flush=True)
        raise


if __name__ == "__main__":
    main()
