"""Regression checks for agent package auto-preflight on Debian/Proxmox."""
import json
from pathlib import Path
from scripts import mta_proxmox_gpu_preflight as pre


class Result:
    def __init__(self, text):
        self.stdout = text


def test_amd_smi_2452_with_gpu_and_process():
    def run(cmd, **kw):
        if cmd[-1] == 'list':
            return Result('GPU: 0\n    BDF: 0000:c5:00.0\n')
        return Result(json.dumps([{'gpu': 0, 'process_info': {'pid': 21729}}]))
    assert pre.probe(run)[0]


def test_idle_gpu_is_accepted():
    def run(cmd, **kw):
        return Result('GPU: 0\n') if cmd[-1] == 'list' else Result('[]')
    assert pre.probe(run)[0]


def test_no_gpu_disables_telemetry():
    def run(cmd, **kw):
        return Result('No GPUs')
    assert not pre.probe(run)[0]


def test_invalid_process_json_fails_closed():
    def run(cmd, **kw):
        return Result('GPU: 0\n') if cmd[-1] == 'list' else Result('{"invalid":true}')
    assert not pre.probe(run)[0]


def test_missing_binary_fails_closed():
    def run(cmd, **kw):
        raise FileNotFoundError('amd-smi')
    assert not pre.probe(run)[0]


def test_package_preflight_and_dependencies():
    text = (Path(__file__).resolve().parents[1] / 'packaging/proxmox-gpu-agent/build_deb.sh').read_text()
    assert 'amd-smi' in text and 'pve-container' in text and 'acl' in text
    assert 'ExecCondition=/usr/bin/python3 /usr/lib/mta-proxmox-gpu-agent/preflight.py' in text
    assert 'MTA GPU telemetry unavailable;' in text
    import re
    version = re.search(r'^VERSION=(0\.3\.0-208\.\d+)$', text, re.MULTILINE)
    assert version, 'Expected a valid r208 Proxmox agent package version'


def test_amd_smi_2452_idle_literal_is_accepted():
    def run(cmd, **kw):
        if cmd[-1] == 'list':
            return Result('GPU: 0\n')
        return Result(json.dumps([{'gpu': 0, 'process_info': 'No running processes detected'}]))
    assert pre.probe(run)[0]

def test_unknown_process_info_string_is_rejected():
    def run(cmd, **kw):
        if cmd[-1] == 'list':
            return Result('GPU: 0\n')
        return Result(json.dumps([{'gpu': 0, 'process_info': 'unexpected error'}]))
    assert not pre.probe(run)[0]
