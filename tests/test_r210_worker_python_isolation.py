"""Real subprocess checks for startup import injection in worker boundaries."""
import json
import os
from pathlib import Path
import subprocess
import sys
import shutil

import pytest
from app import ai_execution_policy,ai_process_guard,ai_worker_protocol


def poisoned_pythonpath(tmp_path):
    payload=tmp_path/'poison';payload.mkdir();marker=tmp_path/'startup-executed'
    (payload/'sitecustomize.py').write_text('from pathlib import Path\nPath('+repr(str(marker))+').write_text("unexpected")\n')
    return payload,marker


@pytest.mark.skipif(sys.platform!='linux',reason='Linux guardian boundary')
def test_real_guardian_ignores_inherited_pythonpath_before_startup(tmp_path,monkeypatch):
    payload,marker=poisoned_pythonpath(tmp_path);monkeypatch.setenv('PYTHONPATH',str(payload))
    clean=tmp_path/'clean';clean.mkdir()
    result=ai_process_guard.run([sys.executable,'-I','-c','pass'],cwd=clean,timeout_seconds=10,env={})
    assert result.exit_code==0 and result.tree_complete
    assert not marker.exists()


def test_actual_ace_capability_worker_ignores_inherited_pythonpath(tmp_path):
    payload,marker=poisoned_pythonpath(tmp_path)
    adapter=Path(ai_worker_protocol.__file__).with_name('ace_step_http_worker.py').resolve()
    env={**os.environ,'PYTHONPATH':str(payload)}
    result=subprocess.run(ai_worker_protocol.worker_command(adapter)+['--capabilities'],env=env,cwd=tmp_path,
                          capture_output=True,timeout=10,check=True)
    assert json.loads(result.stdout)['protocol']=='mta.ai.worker.v1'
    assert not marker.exists()


def test_environment_preserves_policy_and_gpu_but_removes_startup_overrides(monkeypatch):
    original={'PYTHONPATH':'bad','pythonhome':'bad','LD_PRELOAD':'bad',b'PYTHONUSERBASE':b'bad',
              'MTA_AI_ADMITTED_POLICY':'accepted','HIP_VISIBLE_DEVICES':'0','LD_LIBRARY_PATH':'gpu'}
    assert ai_execution_policy.isolated_env(original)=={'MTA_AI_ADMITTED_POLICY':'accepted',
           'HIP_VISIBLE_DEVICES':'0','LD_LIBRARY_PATH':'gpu'}
    assert original['PYTHONPATH']=='bad'
    monkeypatch.setenv('MTA_TEST_INHERITED','yes')
    assert ai_execution_policy.isolated_env({})=={}
    assert ai_execution_policy.isolated_env()['MTA_TEST_INHERITED']=='yes'


def test_actual_ace_capability_probe_filters_inherited_environment(tmp_path,monkeypatch):
    payload,marker=poisoned_pythonpath(tmp_path)
    monkeypatch.setenv('PYTHONPATH',str(payload))
    monkeypatch.setenv('MTA_AI_WORKER_ENABLED','true')
    monkeypatch.setenv('MTA_AI_WORKER_EXECUTABLE',str(Path(ai_worker_protocol.__file__).with_name('ace_step_http_worker.py').resolve()))
    assert ai_worker_protocol.probe_worker(timeout_seconds=10)['probe_ok']
    assert not marker.exists()


def test_real_demucs_capability_probe_ignores_inherited_pythonpath(tmp_path,monkeypatch):
    from app import demucs_runtime
    payload,marker=poisoned_pythonpath(tmp_path)
    monkeypatch.setenv('PYTHONPATH',str(payload))
    demucs_runtime._installed.cache_clear()
    demucs_runtime._installed(sys.executable,0)
    assert not marker.exists()


@pytest.mark.skipif(sys.platform!='linux' or not shutil.which('cc'),reason='Linux C compiler required')
def test_real_guardian_removes_dynamic_loader_preload(tmp_path,monkeypatch):
    marker=tmp_path/'preloaded'
    source=tmp_path/'preload.c'
    library=tmp_path/'preload.so'
    source.write_text('#include <stdio.h>\n__attribute__((constructor)) static void injected(void) '
                      '{FILE *f=fopen('+json.dumps(str(marker))+',"w"); if(f){fputs("unexpected",f);fclose(f);}}\n')
    subprocess.run([shutil.which('cc'),'-shared','-fPIC',str(source),'-o',str(library)],check=True)
    monkeypatch.setenv('LD_PRELOAD',str(library))
    # Prove the payload works in this environment before checking the guardian.
    subprocess.run([sys.executable,'-I','-c','pass'],check=True)
    assert marker.exists()
    marker.unlink()
    clean=tmp_path/'clean';clean.mkdir()
    result=ai_process_guard.run([sys.executable,'-I','-c','pass'],cwd=clean,timeout_seconds=10,env={})
    assert result.exit_code==0 and result.tree_complete
    assert not marker.exists()


@pytest.mark.skipif(sys.platform!='linux',reason='Linux guardian boundary')
def test_guardian_preserves_admitted_values_for_actual_child(tmp_path,monkeypatch):
    payload,marker=poisoned_pythonpath(tmp_path)
    monkeypatch.setenv('PYTHONPATH',str(payload))
    output=tmp_path/'policy'
    code='import os,pathlib;pathlib.Path('+repr(str(output))+').write_text(os.environ["MTA_TEST_POLICY"])'
    result=ai_process_guard.run([sys.executable,'-c',code],cwd=tmp_path,timeout_seconds=10,
                                env={'PYTHONPATH':str(payload),'MTA_TEST_POLICY':'accepted'})
    assert result.exit_code==0 and result.tree_complete
    assert output.read_text()=='accepted'
    assert not marker.exists()
