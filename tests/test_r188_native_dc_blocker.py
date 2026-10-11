import shutil
import subprocess
import tempfile
from pathlib import Path
import pytest


def test_native_dc_blocker_compiles_and_processes():
    compiler = shutil.which('c++')
    if not compiler:
        pytest.skip('C++ compiler unavailable')
    root = Path(__file__).resolve().parents[1]
    code = '''#include "native_dc_blocker.hpp"
#include <cmath>
#include <limits>
int main() {
 mta::NativeDcBlocker bad(9);
 if (bad.valid()) return 1;
 mta::NativeDcBlocker filter(2);
 if (!filter.valid()) return 2;
 float audio[1024];
 for (auto& sample: audio) sample = 0.5f;
 for (int iteration=0; iteration<20; ++iteration)
   if (!filter.process(audio, 512)) return 3;
 // Restart fixed DC input after every processing block.
 for (int iteration=0; iteration<20; ++iteration) {
   for (auto& sample: audio) sample = 0.5f;
   if (!filter.process(audio, 512)) return 4;
 }
 if (std::fabs(audio[1023]) > 0.001f) return 5;
 filter.reset();
 float broken[2] = {std::numeric_limits<float>::quiet_NaN(), 0.0f};
 if (filter.process(broken, 1)) return 6;
 return 0;
}'''
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / 'test.cpp'
        source.write_text(code)
        binary = Path(directory) / 'test'
        subprocess.run([compiler, '-std=c++20', '-Wall', '-Wextra', '-Werror', '-I',
                        str(root / 'native/audio_core'), str(source), '-o', str(binary)],
                       check=True, capture_output=True)
        subprocess.run([str(binary)], check=True, capture_output=True)
