"""Opt-in SAM Audio CLI worker. Requires authorized Hugging Face access.

Install from https://github.com/facebookresearch/sam-audio in a separate venv.
No checkpoints are shipped with MTA Audio Editor.
"""
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--prompt", required=True)
    args = parser.parse_args()
    import torch
    import torchaudio
    from sam_audio import SAMAudio, SAMAudioProcessor
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = SAMAudio.from_pretrained(args.model).eval().to(device)
    processor = SAMAudioProcessor.from_pretrained(args.model)
    inputs = processor(audios=[args.source], descriptions=[args.prompt]).to(device)
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
