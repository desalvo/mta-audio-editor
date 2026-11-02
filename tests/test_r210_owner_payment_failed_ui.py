"""The error path retains the latest server-verified owner history."""
import shutil
import subprocess
from pathlib import Path

import pytest


def test_failed_verification_refreshes_history_and_keeps_controls():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node required')
    root = Path(__file__).resolve().parents[1]
    subprocess.run([node, str(root / 'tests/js/owner_payments_failed_verification.cjs')],
                   cwd=root, check=True, capture_output=True, text=True, timeout=20)
