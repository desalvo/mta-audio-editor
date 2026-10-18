"""Opt-in SAM Audio CLI worker. Requires authorized Hugging Face access.

Install from https://github.com/facebookresearch/sam-audio in a separate venv.
No checkpoints are shipped with MTA Audio Editor.
"""
import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--anchors-json", default="")
    args = parser.parse_args()
    stage = "imports"
    try:
        import torch
        import torchaudio
        from sam_audio import SAMAudio, SAMAudioProcessor
        device = "cuda" if torch.cuda.is_available() else "cpu"
        if __package__:
            from .sam_audio_compat import sam_hub_compat
        else:
            from sam_audio_compat import sam_hub_compat
        stage = "model_load"
        with sam_hub_compat():
            model = SAMAudio.from_pretrained(args.model).eval().to(device)
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
    except Exception:
        print("MTA_SAM_FAILURE:" + stage, file=sys.stderr, flush=True)
        raise


if __name__ == "__main__":
    main()
