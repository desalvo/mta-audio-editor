from pathlib import Path


def test_pyinstaller_spec_uses_repository_root_from_spec_directory():
    root = Path(__file__).resolve().parents[1]
    spec = (root / "native/mta_audio_editor_native.spec").read_text(encoding="utf-8")
    assert "project = Path(SPECPATH).parent" in spec
    assert "project = Path(SPECPATH).parent.parent" not in spec
    assert 'project / "native" / "mta_audio_editor_native.py"' in spec
    assert 'project / "app" / "templates"' in spec
    assert 'project / "VERSION"' in spec
    assert 'project / "BUILD_INFO"' in spec
