#!/usr/bin/env python3
"""Export a Demucs model wrapper to the Core ML contract used by the iOS client.

This is an optional developer utility. It requires a macOS Python environment with
PyTorch, demucs, and coremltools installed. The resulting model contract is:
  input  "audio" : Float32 [1, 2, chunk_frames]
  output "stems" : Float32 [1, stem_count, 2, chunk_frames]
Creator-defined metadata declares stem_count, stem_labels, sample_rate, chunk_frames,
input_name and output_name.
"""
from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="htdemucs")
    parser.add_argument("--stem-count", type=int, choices=(2,4,6,8), required=True)
    parser.add_argument("--chunk-seconds", type=float, default=10.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        import torch
        import numpy as np
        import coremltools as ct
        from demucs.pretrained import get_model
    except ImportError as exc:
        raise SystemExit("Install torch, demucs and coremltools in a macOS export environment") from exc

    model = get_model(args.model)
    model.eval()
    rate = int(getattr(model, "samplerate", 44100))
    frames = int(args.chunk_seconds * rate)

    labels = list(getattr(model, "sources", []))
    if args.stem_count == 2:
        # A dedicated 2-stem export should use a wrapper/model trained or configured
        # for vocals/accompaniment. Do not invent output channels here.
        if len(labels) != 2:
            raise SystemExit("The selected model does not expose exactly 2 sources; export a dedicated 2-stem wrapper")
    if len(labels) != args.stem_count:
        raise SystemExit(f"Model exposes {len(labels)} sources ({labels}), expected {args.stem_count}")

    example = torch.zeros(1, 2, frames, dtype=torch.float32)
    traced = torch.jit.trace(model, example)
    mlmodel = ct.convert(
        traced,
        inputs=[ct.TensorType(name="audio", shape=example.shape, dtype=np.float32)],
        outputs=[ct.TensorType(name="stems")],
        compute_precision=ct.precision.FLOAT16,
        minimum_deployment_target=ct.target.iOS15,
    )
    mlmodel.user_defined_metadata.update({
        "stem_count": str(args.stem_count),
        "stem_labels": ",".join(labels),
        "sample_rate": str(rate),
        "chunk_frames": str(frames),
        "input_name": "audio",
        "output_name": "stems",
        "source_model": args.model,
    })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    mlmodel.save(str(args.output))
    print(args.output)


if __name__ == "__main__":
    main()
