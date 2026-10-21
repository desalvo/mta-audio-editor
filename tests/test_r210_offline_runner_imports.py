"""Actual subprocess imports, independent of model/checkpoint fixtures."""
from pathlib import Path
import subprocess
import sys


def test_runtime_namespace_is_not_shadowed_by_mta_i18n(tmp_path):
    runtime=tmp_path/'runtime';(runtime/'i18n').mkdir(parents=True)
    (runtime/'i18n/i18n.py').write_text("marker='runtime'\n")
    script=runtime/'infer.py'
    script.write_text("from i18n.i18n import marker\nassert marker=='runtime'\n")
    wrapper=Path(__file__).resolve().parents[1]/'app/studio_offline_runner.py'
    result=subprocess.run([sys.executable,str(wrapper),str(script)],cwd=runtime,
                          capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stdout+result.stderr
