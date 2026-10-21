"""Optional real DOM implementation; no fabricated browser/inference claims."""
import os,subprocess,shutil
from pathlib import Path
import pytest


def test_extended_studio_dom_flows():
    if not os.getenv('MTA_TEST_DOM_MODULE'):pytest.skip('Install optional happy-dom and set MTA_TEST_DOM_MODULE to its lib/index.js')
    node=shutil.which('node')
    if not node:pytest.skip('Node is unavailable')
    result=subprocess.run([node,'tests/studio_extended_dom.mjs'],cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stdout+result.stderr
    assert '5 DOM integration workflows passed' in result.stdout
