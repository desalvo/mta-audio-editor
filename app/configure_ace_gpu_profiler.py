#!/usr/bin/env python3
"""Prepare an opt-in ACE service override. Never restart or install dependencies."""
from __future__ import annotations
import argparse
from pathlib import Path
import tempfile

MARKER = '# MTA r210 diagnostic GPU profiler\n'


def configure(*, base: Path, wrapper: Path, unit_root: Path, enabled=True, port=8001):
    target = unit_root / 'mta-ace-step.service.d/40-mta-gpu-profiler.conf'
    if target.exists() and not target.read_text().startswith(MARKER):
        raise ValueError('Refusing to replace an unrecognized operator override')
    if not enabled:
        target.unlink(missing_ok=True)
        return target
    if not 1 <= port <= 65535 or not base.is_absolute() or not wrapper.is_absolute():
        raise ValueError('Absolute paths and valid port required')
    python = base / 'venv-ace-step/bin/python'
    if not python.is_file() or not wrapper.is_file():
        raise ValueError('ACE Python or installed MTA profiler wrapper not found')
    def quote(path):
        text = str(path)
        if any(c in text for c in '\n\r\0'):
            raise ValueError('Invalid path')
        return '"' + text.replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'
    content = MARKER + '[Service]\nEnvironment=ACESTEP_QUEUE_WORKERS=1\nExecStart=\nExecStart=' + quote(python) + ' ' + quote(wrapper) + f' --host 127.0.0.1 --port {port} --no-init\n'
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w',dir=target.parent,delete=False) as f:
        temporary = Path(f.name)
        f.write(content)
    temporary.chmod(0o644)
    temporary.replace(target)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',type=Path,default=Path('/opt/mta'))
    parser.add_argument('--wrapper',type=Path,default=Path('/usr/lib/mta-audio-editor-server/app/ace_profile_server.py'))
    parser.add_argument('--unit-root',type=Path,default=Path('/etc/systemd/system'))
    parser.add_argument('--port',type=int,default=8001)
    parser.add_argument('--disable',action='store_true')
    args = parser.parse_args()
    try:
        target = configure(base=args.base,wrapper=args.wrapper,unit_root=args.unit_root,
                           enabled=not args.disable,port=args.port)
    except (ValueError,OSError) as exc:
        parser.exit(1,str(exc)+'\n')
    print(f'Override {"removed" if args.disable else "prepared"}: {target}')
    print('When ACE is idle: systemctl daemon-reload && systemctl restart mta-ace-step.service')


if __name__ == '__main__':
    main()
