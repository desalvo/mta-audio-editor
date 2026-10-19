"""Build the pinned Pedalboard host extension during packaging, never at startup.

All vendor sources stay in the external build cache. The upstream commit and
submodule commits are immutable; MTA ships the small source extension separately.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

from patch_vst3_runtime import patch,UPSTREAM

ROOT=Path(__file__).resolve().parents[1]


def install_wheel(wheel):
    # The wheel is built with --no-deps, but importing it requires NumPy.
    # Preserve existing NumPy 1.x installations on Intel macOS.
    subprocess.run([sys.executable,'-m','pip','install','numpy'],check=True)
    subprocess.run([sys.executable,'-m','pip','install','--no-deps','--force-reinstall',str(wheel)],check=True)
    subprocess.run([sys.executable,'-c','from pedalboard import VST3Plugin; assert all(hasattr(VST3Plugin,n) for n in ("_mta_set_transport","_mta_set_musical_position","_mta_process_sidechain")), "Missing compiled MTA transport ABI"'],check=True)


def build(destination,source=None,*,install=False):
    destination=Path(destination).resolve();destination.mkdir(parents=True,exist_ok=True)
    identity=hashlib.sha256(b''.join((ROOT/name).read_bytes() for name in ('native/host_transport/MtaHostTransport.h','native/host_transport/MtaSidechainMethods.h','native/host_transport/MtaUmpEvents.inc','scripts/patch_vst3_runtime.py'))+json.dumps([UPSTREAM,sys.implementation.cache_tag,platform.system(),platform.machine(),os.getenv('ARCHFLAGS',''),os.getenv('MACOSX_DEPLOYMENT_TARGET','')]).encode()).hexdigest()
    record=destination/'mta-host-build.json'
    wheels=list(destination.glob('pedalboard-0.9.26+mta2-*.whl'))
    cached=False
    if record.exists() and len(wheels)==1:
        previous=json.loads(record.read_text())
        cached=previous.get('identity')==identity and previous.get('sha256')==hashlib.sha256(wheels[0].read_bytes()).hexdigest()
    if not cached:
        managed=source is None
        if source is None:
            source=destination.parent/'vst3-host-source'
            if not source.exists():subprocess.run(['git','clone','--no-checkout','https://github.com/spotify/pedalboard.git',str(source)],check=True)
            subprocess.run(['git','-C',str(source),'checkout','--detach',UPSTREAM],check=True)
            subprocess.run(['git','-C',str(source),'submodule','set-url','vendors/pybind11','https://github.com/pybind/pybind11.git'],check=True)
            subprocess.run(['git','-C',str(source),'submodule','update','--init','--recursive','--jobs','2'],check=True)
        source=Path(source).resolve()
        commit=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
        if commit!=UPSTREAM:raise ValueError('Refusing an unpinned VST host source tree')
        if managed:
            # Restore only files owned by our dedicated vendor cache. A changed
            # host patch must never silently reuse an older compiled extension.
            for name in ('pedalboard/ExternalPlugin.h','pyproject.toml'):
                (source/name).write_bytes(subprocess.check_output(['git','-C',str(source),'show',UPSTREAM+':'+name]))
            juce=source/'JUCE'
            name='modules/juce_audio_processors/format_types/juce_VST3Common.h'
            (juce/name).write_bytes(subprocess.check_output(['git','-C',str(juce),'show','HEAD:'+name]))
        patch(source)
        env={**os.environ,'CMAKE_BUILD_PARALLEL_LEVEL':os.getenv('MTA_VST3_BUILD_JOBS','2')}
        subprocess.run([sys.executable,'-m','pip','wheel','--no-deps','--wheel-dir',str(destination),str(source)],check=True,env=env)
        wheels=list(destination.glob('pedalboard-0.9.26+mta2-*.whl'))
        if len(wheels)!=1:raise ValueError('Expected one platform-specific MTA VST host wheel')
        record.write_text(json.dumps({'identity':identity,'upstream':UPSTREAM,'transport_abi':2,'wheel':wheels[0].name,'sha256':hashlib.sha256(wheels[0].read_bytes()).hexdigest()},indent=2)+'\n')
    if install:
        install_wheel(wheels[0])
    return wheels[0]


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--wheel-dir',type=Path,required=True);parser.add_argument('--source',type=Path);parser.add_argument('--install',action='store_true');args=parser.parse_args()
    print(build(args.wheel_dir,args.source,install=args.install))
