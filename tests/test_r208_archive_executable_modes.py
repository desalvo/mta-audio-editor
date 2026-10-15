"""Regression: reconstructed cumulative ZIPs must retain executable installers."""


from pathlib import Path


def test_packager_restores_shell_entry_point_execute_bits():
    source = (Path(__file__).resolve().parents[1] / "scripts/package.sh").read_text()
    assert "mode |= 0o111" in source
    assert "info.external_attr" in source


def test_all_shell_installers_have_valid_shebang():
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    for script in scripts.glob("*.sh"):
        assert script.read_bytes().startswith(b"#!/"), script.name
