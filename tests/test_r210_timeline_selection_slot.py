"""Regression checks against the production timeline and track templates."""
import shutil
import subprocess
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]

def test_timeline_selection_slots_and_keyboard():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node required')
    subprocess.run([node, 'tests/js/timeline_selection_slot.cjs'], cwd=ROOT, check=True, timeout=20)
