import shutil
import subprocess
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.ai_worker_protocol import run_worker_with_project_audio


def _wav(path):
    with wave.open(str(path), 'wb') as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(44100)
        stream.writeframes(b'\0\0' * 100)


def test_worker_receives_audio_and_returns_preview(monkeypatch, tmp_path, synthetic_worker_resolution):
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER', 'true')
    source = tmp_path / 'source.wav'
    _wav(source)
    worker = tmp_path / 'worker'
    worker.write_text('''#!/usr/bin/env python3
import json,sys,pathlib,shutil
args=sys.argv
req=json.loads(pathlib.Path(args[args.index('--request')+1]).read_text())
assert len(req['source_audio'])==1
input_path=pathlib.Path(req['source_audio'][0]['filename'])
assert input_path.exists()
assert not input_path.is_absolute()
shutil.copyfile(input_path,args[args.index('--output')+1])
''')
    worker.chmod(0o700)
    monkeypatch.setenv('MTA_AI_WORKER_ENABLED', 'true')
    monkeypatch.setenv('MTA_AI_WORKER_EXECUTABLE', str(worker))
    project = SimpleNamespace(id='project1', tracks=[SimpleNamespace(id='t1', filename='source.wav')])
    data, meta = run_worker_with_project_audio({'scope': 'project'}, project, lambda pid, filename: source)
    assert data.startswith(b'RIFF') and meta['sample_rate'] == 44100


def test_source_path_is_not_user_controlled(monkeypatch, tmp_path, synthetic_worker_resolution):
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER', 'true')
    monkeypatch.setenv('MTA_AI_WORKER_ENABLED', 'true')
    exe = tmp_path / 'worker'
    exe.write_text('#!/bin/sh\nexit 0\n')
    exe.chmod(0o700)
    monkeypatch.setenv('MTA_AI_WORKER_EXECUTABLE', str(exe))
    project = SimpleNamespace(id='p', tracks=[SimpleNamespace(id='t', filename='../outside.wav')])
    with pytest.raises(ValueError, match='WAV source'):
        run_worker_with_project_audio({'scope': 'project'}, project, lambda *_: tmp_path / 'outside.wav')


def test_native_dsp_contract_is_present():
    root = Path(__file__).resolve().parents[1]
    assert (root / 'native/audio_core/native_pdc_mix.hpp').is_file()
    assert (root / 'native/audio_core/native_peak_meter.hpp').is_file()


def test_native_preview_crossfade_compiles(tmp_path):
    compiler = shutil.which('g++') or shutil.which('clang++')
    if compiler is None:
        pytest.skip('C++ compiler not available')
    root = Path(__file__).resolve().parents[1]
    source = tmp_path / 'crossfade.cpp'
    source.write_text('''#include "native_crossfade.hpp"
#include <cassert>
#include <cmath>
int main(){mta::audio::NativeCrossfade x;float a[]={1.f,1.f},b[]={0.f,0.f},o[]={0.f,0.f};
assert(x.process(a,b,o,1,2,0.f));assert(o[0]>0.99f);
assert(x.process(a,b,o,1,2,1.f));assert(std::fabs(o[0])<0.00001f);
assert(!x.process(a,b,o,1,2,NAN));}
''')
    binary = tmp_path / 'crossfade'
    subprocess.run([compiler, '-std=c++20', '-Wall', '-Wextra', '-Werror', '-I',
                    str(root / 'native/audio_core'), str(source), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
