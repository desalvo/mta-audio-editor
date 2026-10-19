"""Build and validate the bundled DSP for the current application target; never at startup."""
import argparse
import os
from pathlib import Path
import subprocess
import sys


def build(project,build_dir):
    subprocess.run(['cmake','-S',str(project/'native/audio_core'),'-B',str(build_dir),'-DCMAKE_BUILD_TYPE=Release'],check=True)
    subprocess.run(['cmake','--build',str(build_dir),'--config','Release','--parallel','2'],check=True)
    name='mta_audio_core.dll' if os.name=='nt' else ('libmta_audio_core.dylib' if sys.platform=='darwin' else 'libmta_audio_core.so')
    candidates=[build_dir/name,build_dir/'Release'/name]
    binary=next((p.resolve() for p in candidates if p.is_file()),None)
    if binary is None:raise RuntimeError('Compiled audio core not found')
    env={**os.environ,'MTA_AUDIO_CORE_PATH':str(binary),'PYTHONPATH':str(project)}
    subprocess.run([sys.executable,'-c',"import ctypes,os; lib=ctypes.CDLL(os.environ['MTA_AUDIO_CORE_PATH']); lib.mta_audio_core_abi.restype=ctypes.c_uint; assert lib.mta_audio_core_abi()==1; [getattr(lib,n) for n in ('mta_render_gain','mta_render_mix','mta_render_envelope')]; print('C++ render DSP ABI 1: ready')"],check=True,env=env)
    return binary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir',type=Path,default=Path('build/audio_core'))
    args=parser.parse_args();project=Path(__file__).resolve().parents[1]
    binary=build(project,args.build_dir.resolve())
    if os.getenv('GITHUB_ENV'):
        with Path(os.environ['GITHUB_ENV']).open('a',encoding='utf-8') as f:f.write('MTA_NATIVE_AUDIO_CORE='+str(binary)+'\n')
    print(binary)
