"""Executable UI submission contract; no real browser or synthesis claim."""
import shutil
import subprocess
from pathlib import Path
import pytest


def test_multilingual_neural_submission_does_not_require_oddvoices():
    node=shutil.which('node')
    if not node:pytest.skip('Node is required for executable JS contract')
    root=Path(__file__).resolve().parents[1]
    outcome=subprocess.run([node,'tests/studio_vocal_submission.cjs'],cwd=root,capture_output=True,text=True,timeout=30)
    assert outcome.returncode==0,outcome.stdout+outcome.stderr
    assert '3 multilingual neural UI submission contracts passed' in outcome.stdout
