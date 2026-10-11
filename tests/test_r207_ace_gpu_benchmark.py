from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_probe_only_no_gpu(tmp_path):
    report = tmp_path / 'probe'
    proc = subprocess.run([sys.executable, str(ROOT / 'scripts/ace_gpu_benchmark.py'), '--probe-only', '--output-dir', str(report)], capture_output=True, text=True, timeout=20)
    assert proc.returncode == 0, proc.stderr
    data = json.loads((report / 'gpu-info.json').read_text())
    assert data['schema'] == 1 and 'vendor' in data and 'limitations' in data
    assert not (report / 'gpu-activity.json').exists()


def test_wizard_benchmark_help_and_dryrun():
    script = ROOT / 'scripts/install_ace_step.sh'
    help_ = subprocess.run(['bash', str(script), '--help'], capture_output=True, text=True)
    assert '--benchmark' in help_.stdout
    proc = subprocess.run(['bash', str(script), '--benchmark', '--dry-run', '--benchmark-no-install-tools'], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert 'GPU benchmark mode' in proc.stdout


def test_benchmark_requires_ace_install(tmp_path):
    proc = subprocess.run([sys.executable, str(ROOT / 'scripts/ace_gpu_benchmark.py'), '--ace-root', str(tmp_path / 'absent'), '--python', sys.executable, '--output-dir', str(tmp_path / 'probe')], capture_output=True, text=True)
    assert proc.returncode != 0
    assert 'ACE-Step installation not found' in proc.stderr
