"""Compile the bounded native PDC planner on a real C++20 compiler."""
import shutil
import subprocess
from pathlib import Path

import pytest


def test_native_pdc_plan(tmp_path):
    compiler = shutil.which("g++") or shutil.which("clang++")
    if compiler is None:
        pytest.skip("C++20 compiler unavailable")
    native = Path(__file__).resolve().parents[1] / "native" / "audio_core"
    src = tmp_path / "pdc.cpp"
    src.write_text(r'''
#include "vst3_pdc_plan.hpp"
#include <cassert>
#include <limits>
int main() {
  mta::Vst3PdcRoute routes[3] = {{100,256,0,true},{20,256,0,true},{700,0,0,false}};
  auto p=mta::make_vst3_pdc_plan(routes,3);
  assert(p.valid && p.target_frames==356 && p.count==3);
  assert(p.routes[0].alignment_frames==0);
  assert(p.routes[1].alignment_frames==80);
  assert(p.routes[2].alignment_frames==0);
  mta::Vst3PdcRoute bad[1]={{std::numeric_limits<unsigned>::max(),1,0,true}};
  assert(!mta::make_vst3_pdc_plan(bad,1).valid);
  assert(!mta::make_vst3_pdc_plan(nullptr,1).valid);
  assert(!mta::make_vst3_pdc_plan(routes,65).valid);
  assert(mta::make_vst3_pdc_plan(nullptr,0).valid);
}
''', encoding="utf-8")
    binary = tmp_path / "pdc"
    subprocess.run([compiler, "-std=c++20", "-O2", "-Wall", "-Wextra", "-Werror", "-pedantic", "-I", str(native), str(src), "-o", str(binary)], check=True, timeout=30)
    subprocess.run([str(binary)], check=True, timeout=10)
