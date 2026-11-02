import shutil
import subprocess
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_production_ui_transfer_paths_and_undo_redo():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node required')
    subprocess.run([node, 'tests/js/timeline_cross_track.cjs'], cwd=ROOT, check=True, timeout=30)
