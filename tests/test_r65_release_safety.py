"""Guard native host readiness until interactive IPC and realtime acceptance."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_native_host_remains_explicitly_unready():
    source = (ROOT / 'native/vst3_probe/main.cpp').read_text()
    adapter = (ROOT / 'native/vst3_probe/probe.py').read_text()
    assert r'\"native_host_ready\":false' in source
    assert "'native_host_ready': False" in adapter

def test_build_versions_match_release():
    revision = (ROOT / 'REVISION').read_text().strip()
    assert revision.isdecimal()
    assert (ROOT / 'RELEASE').read_text().strip() == f'0.3.0-r{revision}'
    windows = (ROOT / 'native/windows-version-info.txt').read_text()
    assert f'filevers=(0, 3, 0, {revision})' in windows
    assert f'Revision {revision}' in windows
