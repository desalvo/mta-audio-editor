"""Ensure the release publisher authenticates GitHub's published host key."""
import base64
import hashlib
from pathlib import Path
import re

WORKFLOW = (Path(__file__).resolve().parents[1] / '.github/workflows/server-pages-publish.yml').read_text()


def test_github_pinned_host_key_matches_official_fingerprint():
    match = re.search(r'\[ssh\.github\.com\]:443 ssh-ed25519 ([A-Za-z0-9+/=]+)', WORKFLOW)
    assert match
    digest = base64.b64encode(hashlib.sha256(base64.b64decode(match.group(1))).digest()).decode().rstrip('=')
    assert 'SHA256:' + digest == 'SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU'


def test_deploy_ssh_uses_verified_github_key_and_port_443():
    assert 'HostName ssh.github.com' in WORKFLOW
    assert 'Port 443' in WORKFLOW
    assert 'StrictHostKeyChecking yes' in WORKFLOW
    assert 'ssh-keyscan' not in WORKFLOW.split('Install restricted deploy SSH identity')[1].split('Create signed-channel archive')[0].replace('unauthenticated keyscan', '')
    assert 'PZ7Mtd8Yg7cU6c' not in WORKFLOW
