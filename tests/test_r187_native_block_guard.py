import subprocess
from pathlib import Path
import tempfile
import shutil
import pytest

def test_rt_block_guard_compiles_and_runs():
    compiler = shutil.which('c++')
    if not compiler:
        pytest.skip('No native C++ compiler available')
    root = Path(__file__).resolve().parents[1]
    code = '''#include "native_block_guard.hpp"
#include <limits>
int main() {
    float a[] = {0.25f, 2.f, -2.f, std::numeric_limits<float>::quiet_NaN()};
    if (!mta::sanitize_audio_block(a, 4)) return 1;
    if (a[0] != 0.25f || a[1] != 1.f || a[2] != -1.f || a[3] != 0.f) return 2;
    return mta::sanitize_audio_block(nullptr, 3) ? 3 : 0;
}'''
    with tempfile.TemporaryDirectory() as directory:
        source=Path(directory)/'check.cpp'; source.write_text(code)
        executable=Path(directory)/'check'
        subprocess.run([compiler,'-std=c++20','-Wall','-Wextra','-Werror','-I',str(root/'native/audio_core'),str(source),'-o',str(executable)],check=True,capture_output=True)
        subprocess.run([str(executable)],check=True,capture_output=True)
