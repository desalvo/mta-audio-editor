"""Run a pinned model script with Python network connections denied.

This prevents upstream Python auto-download paths from installing unreviewed
auxiliary assets. It supplements the worker's OS isolation; it is not a sandbox
for malicious administrator-supplied native code.
"""
import runpy
import socket
import sys
from pathlib import Path


def activate():
    def audit(event,args):
        if event=='socket.getaddrinfo':raise PermissionError('Model inference is offline; install every dependency first')
        if event=='socket.connect' and args and getattr(args[0],'family',None) in (socket.AF_INET,socket.AF_INET6):
            raise PermissionError('Model inference is offline; install and authorize every dependency first')
    sys.addaudithook(audit)


def main(checkpoint_guard=False):
    if len(sys.argv)<2:raise ValueError('Pinned model script required')
    script=Path(sys.argv[1]).resolve(strict=True)
    if checkpoint_guard:
        from seed_checkpoint import load_checkpoint
        from seed_audio_export import install_export_guard
    activate();sys.argv=sys.argv[1:]
    # Python puts this wrapper's app/ directory on sys.path. Its flat i18n.py
    # shadows RVC's namespace package i18n/, even when the runtime root is
    # prepended. Upstream scripts must see their own modules, not MTA's.
    wrapper_dir=Path(__file__).resolve().parent
    sys.path[:]=[entry for entry in sys.path
                 if Path(entry or '.').resolve()!=wrapper_dir]
    sys.path.insert(0,str(script.parent));sys.path.insert(0,str(Path.cwd()))
    if checkpoint_guard:
        import modules.commons
        modules.commons.load_checkpoint=load_checkpoint
        install_export_guard()
    runpy.run_path(str(script),run_name='__main__')

if __name__=='__main__':main()
