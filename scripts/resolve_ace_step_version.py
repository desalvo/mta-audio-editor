#!/usr/bin/env python3
"""Resolve an audited ACE-Step release tag to an immutable upstream git SHA."""
import json
import re
import subprocess
import sys
from pathlib import Path

UPSTREAM = "https://github.com/ace-step/ACE-Step-1.5.git"
VERSION_FILE = Path(__file__).resolve().parents[1] / "ace_step_version.json"


def load_tag(path=VERSION_FILE):
    tag = json.loads(Path(path).read_text(encoding="utf-8"))["release_tag"]
    if not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        raise ValueError("Only stable ACE-Step release tags are permitted")
    return tag


def parse_refs(output, tag):
    refs = {ref: sha for sha, ref in (line.split("\t", 1) for line in output.splitlines() if "\t" in line)}
    sha = refs.get(f"refs/tags/{tag}^{{}}") or refs.get(f"refs/tags/{tag}")
    if sha is None or not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("Cannot resolve the selected ACE-Step release tag")
    return sha


def resolve(tag):
    result = subprocess.run(
        ["git", "ls-remote", "--tags", UPSTREAM, f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}"],
        check=True, capture_output=True, text=True, timeout=45,
    )
    return parse_refs(result.stdout, tag)


if __name__ == "__main__":
    tag = load_tag()
    commit = resolve(tag)
    print(commit)
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(f"{tag} {commit}\n", encoding="utf-8")
