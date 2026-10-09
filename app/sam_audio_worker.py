"""Opt-in SAM Audio CLI worker. Requires authorized Hugging Face access.

Install from https://github.com/facebookresearch/sam-audio in a separate venv.
No checkpoints are shipped with MTA Audio Editor.
"""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--anchors-json", default="")
    args = parser.parse_args()
    import torch
    import torchaudio
    from sam_audio import SAMAudio, SAMAudioProcessor
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = SAMAudio.from_pretrained(args.model).eval().to(device)
    processor = SAMAudioProcessor.from_pretrained(args.model)
    prompt_args = {"audios": [args.source], "descriptions": [args.prompt]}
    if args.anchors_json:
        anchors = json.loads(args.anchors_json)
        if not isinstance(anchors, list) or not anchors or any(not isinstance(anchor, list) or len(anchor) != 3 or anchor[0] not in {"+", "-"} for anchor in anchors):
            raise ValueError("Invalid SAM Audio temporal anchors")
        prompt_args["anchors"] = [anchors]
    inputs = processor(**prompt_args).to(device)
    with torch.inference_mode():
        result = model.separate(inputs, predict_spans=False, reranking_candidates=1)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    audio = result.target.detach().cpu()
    if audio.ndim == 3 and audio.shape[0] == 1:
        audio = audio[0]
    torchaudio.save(str(path), audio, processor.audio_sampling_rate)


if __name__ == "__main__":
    main()
