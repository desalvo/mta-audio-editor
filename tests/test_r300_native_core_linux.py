from pathlib import Path
import math

ROOT = Path(__file__).resolve().parents[1]


def test_native_meter_fallback_and_rejections():
    from app import native_dsp
    peak, rms = native_dsp.pcm_meter([0.0, -0.5, 0.5, 0.0], channels=2)
    assert math.isclose(peak, 0.5, rel_tol=1e-6)
    assert math.isclose(rms, math.sqrt(0.125), rel_tol=1e-6)
    for invalid, channel in (([], 1), ([1], 2), ([float('nan')], 1)):
        try:
            native_dsp.pcm_meter(invalid, channel)
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid PCM samples accepted')


def test_linux_ci_has_two_native_architectures_and_two_formats():
    ci = (ROOT / '.github/workflows/ci-cd.yml').read_text()
    script = (ROOT / 'scripts/package_native_linux.sh').read_text()
    assert 'ubuntu-24.04-arm' in ci
    assert 'native-linux:' in ci
    assert 'native-linux, mobile-android' in ci
    assert 'dpkg-deb --build' in script
    assert 'rpmbuild ' in script
    assert '.rpm' in script and '.deb' in script


def test_vst3_status_in_native_settings():
    js = (ROOT / 'app/static/app.js').read_text()
    assert 'openNativeVst3Manager()' in js
    assert '/api/vst3/plugins' in js
