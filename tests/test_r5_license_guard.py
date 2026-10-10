from pathlib import Path
import tempfile

from scripts.license_gate import audit

ROOT = Path(__file__).resolve().parents[1]


def test_source_license_gate():
    result = audit(ROOT)
    assert result['ok'], result['errors']


def test_rejects_bundled_unreviewed_vst3():
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        (root / 'THIRD_PARTY_NOTICES.md').write_text('EUPL FFmpeg Chordino VST3')
        plugin = root / 'suspicious.vst3'
        plugin.mkdir()
        (plugin / 'binary.so').write_bytes(b'123')
        result = audit(root)
        assert not result['ok']
        assert any('bundle' in e for e in result['errors'])


def test_rejects_android_notice_removal():
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        (root / 'THIRD_PARTY_NOTICES.md').write_text('EUPL FFmpeg Chordino VST3')
        target = root / 'mobile/android/app/build.gradle.kts'
        target.parent.mkdir(parents=True)
        target.write_text('resources.excludes += setOf("META-INF/LICENSE*", "META-INF/NOTICE*")')
        assert not audit(root)['ok']
