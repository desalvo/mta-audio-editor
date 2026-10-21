#!/usr/bin/env python3
"""Validate a release-time snapshot of ACE-Step source (not checkpoint licensing)."""
from __future__ import annotations
import argparse
import re
from pathlib import Path

WEIGHT_EXTENSIONS = {".safetensors", ".ckpt", ".pt", ".pth", ".gguf", ".onnx"}


def verify(root: Path) -> str:
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Missing or symlinked ACE-Step source directory")
    commit = (root / "UPSTREAM_COMMIT").read_text(encoding="utf-8").strip()
    if re.fullmatch(r"[a-fA-F0-9]{40}", commit) is None:
        raise ValueError("Missing full upstream commit SHA")
    license_text = (root / "LICENSE").read_text(encoding="utf-8")
    if "MIT License" not in license_text or "Permission is hereby granted" not in license_text:
        raise ValueError("ACE-Step source license must be reviewed and MIT")
    if not (root / "pyproject.toml").is_file():
        raise ValueError("Expected upstream Python project metadata is absent")
    if not (root / "acestep").is_dir():
        raise ValueError("Expected ACE-Step Python package is absent")
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"Unexpected source symlink: {path.relative_to(root)}")
        if path.is_file() and (path.suffix.lower() in WEIGHT_EXTENSIONS or "checkpoints" in path.parts):
            raise ValueError(f"Model weight/checkpoint bundled: {path.relative_to(root)}")
    return commit.lower()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    print("Verified ACE-Step source:", verify(args.source))


if __name__ == "__main__":
    main()
