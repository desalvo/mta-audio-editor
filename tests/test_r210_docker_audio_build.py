"""Compile the core with Docker's isolated COPY layout and Win32 macro pressure."""
import ctypes
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.skipif(sys.platform!='linux' or not shutil.which('cmake'),reason='Linux compiler/CMake required for Docker stage replay')
@pytest.mark.parametrize('windows_macros',[False,True],ids=['docker-copy-layout','windows-min-max'])
def test_docker_audio_stage_is_self_contained(tmp_path,windows_macros):
    stage=tmp_path/'root';stage.mkdir()
    # Replay the actual first Docker stage's COPY operations. No checkout paths
    # enter the compiler include search, which reproduces the missing header.
    entered=False
    for line in (ROOT/'Dockerfile').read_text().splitlines():
        if line.startswith('FROM '):
            if entered:break
            entered=True
        if line.startswith('COPY '):
            _,source,destination=shlex.split(line)
            source=ROOT/source;destination=stage/destination.lstrip('/')
            destination.parent.mkdir(parents=True,exist_ok=True)
            if source.is_dir():shutil.copytree(source,destination)
            else:shutil.copy2(source,destination)
    source=stage/'src/audio_core'
    if windows_macros:
        # Inject after system headers, at the same boundary where application
        # expressions see Win32's function-like macros on MSVC.
        unit=source/'device_transport.cpp';text=unit.read_text()
        marker='static_assert(std::atomic<uint64_t>::is_always_lock_free);'
        assert marker in text
        unit.write_text(text.replace(marker,'#define min(a,b) MTA_WIN32_MIN_MACRO_EXPANDED\n#define max(a,b) MTA_WIN32_MAX_MACRO_EXPANDED\n'+marker))
    build=tmp_path/'build'
    subprocess.run(['cmake','-S',str(source),'-B',str(build),'-DCMAKE_BUILD_TYPE=Release'],check=True)
    subprocess.run(['cmake','--build',str(build),'--parallel','2'],check=True)
    core=ctypes.CDLL(str(build/'libmta_audio_core.so'))
    core.mta_audio_core_abi.restype=ctypes.c_uint
    core.mta_transport_abi.restype=ctypes.c_uint
    assert core.mta_audio_core_abi()==core.mta_transport_abi()==1
    for name in ('mta_render_gain','mta_render_mix','mta_transport_open','mta_capture_open'):
        assert getattr(core,name)
