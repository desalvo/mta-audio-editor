"""Run a pinned model script with Python network connections denied.

This prevents upstream Python auto-download paths from installing unreviewed
auxiliary assets. It supplements the worker's OS isolation; it is not a sandbox
for malicious administrator-supplied native code.
"""
import runpy
import os
import socket
import sys
from pathlib import Path


def activate():
    def audit(event,args):
        if event=='socket.getaddrinfo':raise PermissionError('Model inference is offline; install every dependency first')
        if event=='socket.connect' and args and getattr(args[0],'family',None) in (socket.AF_INET,socket.AF_INET6):
            raise PermissionError('Model inference is offline; install and authorize every dependency first')
    sys.addaudithook(audit)


def authorize_script(script,checkpoint_guard=False):
    """A fixed MTA component role is required before executing operator code.

    The role selects checks, not permission. Original installed bindings and
    every current component policy are independently verified in this child.
    """
    role=os.getenv('MTA_STUDIO_OFFLINE_KIND','')
    if role in ('seed-vc','rvc'):
        if checkpoint_guard != (role=='seed-vc'):
            raise ValueError('Offline checkpoint guard does not match component')
        from app.studio_asset_registry import manifest,policies,binding
        asset=os.getenv('MTA_STUDIO_CONVERSION_ASSET_ID','')
        value=manifest(asset,verify=True)
        if (value['kind']!=role or not value['enabled']
                or binding(value,'script').resolve(strict=True)!=script
                or binding(value,'runtime_root').resolve(strict=True)!=Path.cwd().resolve()):
            raise ValueError('Offline script does not match original installed component')
        policies(asset,verify=True)
        return
    if role!='diffsinger' or checkpoint_guard:
        raise ValueError('Explicit supported offline component required')
    from app.model_license_policy import evaluate_singing_components
    evaluate_singing_components()
    model_format=os.getenv('MTA_DIFFSINGER_FORMAT','native')
    if model_format=='openutau-onnx':
        expected=Path(__file__).with_name('diffsinger_onnx.py').resolve()
    elif model_format=='native':
        expected=(Path(os.environ['MTA_DIFFSINGER_ROOT'])/'scripts'/'infer.py').resolve(strict=True)
    else:
        raise ValueError('Unsupported offline singing format')
    if script!=expected:
        raise ValueError('Offline singing script is not the selected runtime')


def main(checkpoint_guard=False):
    if len(sys.argv)<2:raise ValueError('Pinned model script required')
    script=Path(sys.argv[1]).resolve(strict=True)
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    authorize_script(script,checkpoint_guard)
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
