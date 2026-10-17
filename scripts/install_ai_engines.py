#!/usr/bin/env python3
"""Default complete server AI installation, isolated from the web and ACE runtimes.

Invoked by install_mta.sh's signed-package wizard. Model checkpoints are cached
on demand, as in native builds; SAM access remains subject to upstream approval.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE))
from app.ai_install_catalog import ENGINE_GROUPS, IMPORTS, validate_coverage


REQS = ('requirements.txt', 'requirements-stems.txt', 'requirements-lyrics.txt', 'requirements-chords.txt')
SAM_REPO = 'https://github.com/facebookresearch/sam-audio.git'


def selected_device(value):
    if value != 'auto':
        return value
    if Path('/dev/kfd').exists() and list(Path('/dev/dri').glob('renderD*')):
        return 'rocm'
    return 'cuda' if Path('/dev/nvidiactl').exists() else 'cpu'


def run(args, **kwargs):
    print('AI setup:', ' '.join(map(str, args)), flush=True)
    return subprocess.run(list(map(str, args)), check=True, umask=0o022, **kwargs)


def torch_arguments(device):
    if device == 'rocm':
        return ['torch==2.11.0+rocm7.2', 'torchaudio==2.11.0+rocm7.2',
                'torchvision==0.26.0+rocm7.2', '--index-url', 'https://download.pytorch.org/whl/rocm7.2']
    if device == 'cpu':
        return ['torch==2.14.1+cpu', 'torchaudio==2.14.1+cpu', 'torchvision==0.29.1+cpu',
                '--index-url', 'https://download.pytorch.org/whl/cpu']
    return ['torch==2.14.1', 'torchaudio==2.14.1', 'torchvision==0.29.1']


def system_dependencies():
    if shutil.which('dnf'):
        run(['dnf', 'install', '-y', 'git', 'gcc', 'gcc-c++', 'make', 'cmake', 'pkgconf-pkg-config',
             'python3.12-devel', 'libsndfile', 'ffmpeg'])
    elif shutil.which('apt-get'):
        run(['apt-get', 'update'])
        run(['apt-get', 'install', '-y', 'git', 'build-essential', 'cmake', 'pkg-config',
             'python3-dev', 'python3-venv', 'libsndfile1', 'ffmpeg'])
    else:
        raise RuntimeError('Unsupported package manager')


def install_group(python, folder, device, group):
    # Use final, versioned venv path: moving a venv breaks its absolute shebangs.
    # Existing active environments are untouched until the complete preflight passes.
    run([python, '-m', 'venv', folder])
    binary = folder / 'bin/python'
    pip = [binary, '-m', 'pip', 'install', '--disable-pip-version-check']
    run(pip + ['--upgrade', 'pip', 'setuptools', 'wheel'])
    run(pip + torch_arguments(device))
    constraints = folder / 'torch-constraints.txt'
    versions = run([binary, '-c',
        'import importlib.metadata as m;print("\\n".join(n+"=="+m.version(n) for n in ("torch","torchaudio","torchvision")))'],
        capture_output=True, text=True).stdout
    constraints.write_text(versions)
    if group == 'audio':
        # Keep the native requirements as the source of truth. Only the accelerator
        # triplet is selected separately; never replace an existing ACE torch build.
        lines = []
        for name in REQS:
            for line in (SOURCE / name).read_text().splitlines():
                if line.startswith(('--extra-index-url ', 'torch==', 'torchvision==', 'torchaudio==')):
                    continue
                lines.append(line)
        requirements = folder / 'native-ai-requirements.txt'
        requirements.write_text('\n'.join(lines) + '\n')
        run(pip + ['-c', constraints, '-r', requirements])
        run(pip + ['--no-deps', '-r', SOURCE / 'requirements-roformer-compat.txt'])
        # Match native CI's explicit dependencies absent from separator wheel metadata.
        run(pip + ['-c', constraints, 'audioread>=3,<4', 'onnxruntime>=1.17', 'six>=1.16,<2'])
    else:
        # Resolve an immutable official upstream commit and retain it with the
        # installed runtime. This is a read-only query, not a repository mutation.
        revision = run(['git', 'ls-remote', SAM_REPO, 'HEAD'], capture_output=True, text=True).stdout.split()[0]
        import re
        if not re.fullmatch('[a-f0-9]{40}', revision):
            raise ValueError('Invalid SAM upstream revision')
        (folder / 'sam-source-revision').write_text(revision + '\n')
        run(pip + ['-c', constraints, '-r', SOURCE / 'requirements.txt'])
        run(pip + ['-c', constraints, 'sam_audio @ git+' + SAM_REPO + '@' + revision])
    verify(binary, group, device)
    return binary


def verify(binary, group, device=None):
    run([binary, '-c',
         'import importlib,json,sys;[importlib.import_module(n) for n in json.loads(sys.argv[1])]',
         json.dumps(IMPORTS[group])])
    if device in ('rocm', 'cuda'):
        run([binary, '-c', "import torch;assert torch.cuda.is_available(), 'GPU unavailable to AI runtime';" +
             ("assert torch.version.hip, 'ROCm build required';" if device == 'rocm' else '') +
             "x=torch.ones(4,device='cuda');y=x+x;torch.cuda.synchronize();assert y.sum().item()==8"])
    # Exercise the compiled vision operator and reject mismatched wheel triplets.
    run([binary, '-c', 'import torch;from torchvision.ops import nms;assert nms(torch.empty((0,4)),torch.empty(0),0.5).numel()==0'])


def update_environment(path, values, original):
    if path.is_symlink() or (path.read_text() if path.exists() else '') != original:
        raise ValueError('Server configuration changed; rerun AI setup')
    lines = [line for line in original.splitlines() if line.split('=', 1)[0] not in values]
    for key, value in values.items():
        if any(c in value for c in '\r\n\x00'):
            raise ValueError('Unsafe AI setting')
        lines.append(key + '="' + value.replace('\\', '\\\\').replace('"', '\\"') + '"')
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.all-ai-')
    try:
        os.fchmod(fd, 0o600)
        if path.exists():
            info = path.stat()
            os.fchown(fd, info.st_uid, info.st_gid)
        with os.fdopen(fd, 'w') as stream:
            stream.write('\n'.join(lines) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def install(args):
    validate_coverage()
    device = selected_device(args.device)
    plan = {'engines': ENGINE_GROUPS, 'device': device, 'weights': 'on-demand',
            'isolated_runtimes': ['audio', 'sam'], 'gpu_billing_activated': False}
    if args.dry_run:
        print(json.dumps(plan, indent=2))
        return plan
    config = Path(args.env_file)
    if config.is_symlink() or not config.is_file():
        raise ValueError('Existing regular server environment file required')
    original = config.read_text()
    system_dependencies()
    fingerprint = hashlib.sha256((device + json.dumps(ENGINE_GROUPS, sort_keys=True) + Path(__file__).read_text() +
        ''.join((SOURCE / name).read_text() for name in (*REQS, 'requirements-roformer-compat.txt'))).encode()).hexdigest()[:16]
    root = Path(args.base) / ('ai-' + fingerprint)
    root.mkdir(parents=True, exist_ok=True, mode=0o755)
    values = {'MTA_AI_WORKER_ENABLED': 'true', 'MTA_AI_UNIFIED_WORKERS_ENABLED': 'true',
              'MTA_AI_SAM_MODEL': 'facebook/sam-audio-small'}
    defaults = {'MTA_AI_SAM_MODEL': 'facebook/sam-audio-small',
                'MTA_AI_VOCAL_MODEL': 'UVR_MDXNET_KARA_2.onnx',
                'MTA_AI_VOCAL_MODELS_DIR': '/var/lib/mta/models/audio-separator',
                'MTA_DRUMSEP_MODEL_DIR': '/var/lib/mta/models/drumsep',
                'HF_HOME': '/var/lib/mta/models/huggingface'}
    existing = {line.split('=', 1)[0] for line in original.splitlines()}
    values.pop('MTA_AI_SAM_MODEL')
    values.update({key: value for key, value in defaults.items() if key not in existing})
    for group in ('audio', 'sam'):
        folder = root / group
        marker = folder / '.mta-ai-ready.json'
        binary = folder / 'bin/python'
        if marker.is_file() and binary.is_file():
            verify(binary, group, device)
        else:
            binary = install_group(args.python, folder, device, group)
            marker.write_text(json.dumps({'group': group, 'fingerprint': fingerprint, 'device': device}))
        for kind, assigned in ENGINE_GROUPS.items():
            if assigned == group:
                values['MTA_AI_WORKER_' + kind.upper().replace('-', '_') + '_PYTHON'] = str(binary)
        if group == 'audio':
            values['MTA_DEMUCS_PYTHON'] = str(binary)
            if 'MTA_AI_DEFAULT_PYTHON' not in existing:
                values['MTA_AI_DEFAULT_PYTHON'] = str(binary)
        else:
            values['MTA_SAM_AUDIO_PYTHON'] = str(binary)
    # ACE is installed/started by the existing wizard; leave its runtime and URL intact.
    update_environment(config, values, original)
    print(json.dumps({**plan, 'runtime': str(root), 'imports_verified': True}), flush=True)
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python', default=sys.executable)
    parser.add_argument('--base', default='/opt/mta')
    parser.add_argument('--env-file', default='/etc/mta/mta.env')
    parser.add_argument('--device', choices=('auto', 'cpu', 'cuda', 'rocm'), default='auto')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    install(args)


if __name__ == '__main__':
    main()
