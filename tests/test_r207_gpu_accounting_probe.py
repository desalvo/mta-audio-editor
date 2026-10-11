from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / 'scripts/gpu_accounting_probe.py'

def test_gpu_accounting_probe_is_stdlib_and_has_no_host_power_billing():
    source = PROBE.read_text()
    assert 'drm-engine-' in source
    assert 'drm-client-id' in source
    assert 'not billable GPU time' in source
    assert 'gpu_energy_joules' not in source
    assert 'os.environ' not in source

def test_gpu_accounting_probe_parses_deduplicated_process(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('probe', PROBE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'PROC', tmp_path)
    fdinfo = tmp_path / '123' / 'fdinfo'
    fdinfo.mkdir(parents=True)
    rows = 'drm-driver: amdgpu\ndrm-client-id: 7\ndrm-engine-gfx: 120 ns\ndrm-resident-vram: 4 KiB\n'
    (fdinfo / '3').write_text(rows)
    (fdinfo / '4').write_text(rows)
    sample = module.drm_sample(123)
    assert sample['clients'] == 1
    assert sample['metrics']['engine_gfx'] == 120
    assert sample['metrics']['resident_vram'] == 4
