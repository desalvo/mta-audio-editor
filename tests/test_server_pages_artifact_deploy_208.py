from pathlib import Path
import importlib.util
import io
import json
import subprocess
import tarfile
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "packaging/pages-repository/scripts/assemble_pages.py"
SPEC = importlib.util.spec_from_file_location("mta_pages_assembler", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def test_target_workflow_uses_pages_artifact():
    wf = (ROOT / "packaging/pages-repository/.github/workflows/pages.yml").read_text()
    assert "actions/upload-pages-artifact@v4" in wf
    assert "actions/deploy-pages@v4" in wf
    assert "MTA_SOURCE_ARTIFACT_TOKEN" in wf
    assert "gh" in wf


def test_reject_invalid_manifest(tmp_path):
    p = tmp_path / "early.json"
    p.write_text(json.dumps({"schema": 1, "channel": "early", "repository": "untrusted/repo", "run_id": 1, "commit": "a" * 40, "sha256": "b" * 64}))
    with pytest.raises(ValueError, match="Invalid"):
        MOD.load_manifest(p, "early")


def test_reject_tar_escape(tmp_path):
    archive = tmp_path / "bad.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        entry = tarfile.TarInfo("../../outside.txt")
        content = b"BAD"
        entry.size = len(content)
        tar.addfile(entry, io.BytesIO(content))
    with pytest.raises(ValueError, match="Unexpected|escape"):
        MOD.safe_extract(archive, tmp_path / "site", "early")


def test_reject_other_channel(tmp_path):
    archive = tmp_path / "bad.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        entry = tarfile.TarInfo("apt/stable/Packages")
        content = b"BAD"
        entry.size = len(content)
        tar.addfile(entry, io.BytesIO(content))
    with pytest.raises(ValueError, match="Unexpected"):
        MOD.safe_extract(archive, tmp_path / "site", "early")


def test_target_script_compiles_and_publisher_yaml_parses():
    subprocess.run(["python", "-m", "py_compile", str(SCRIPT)], check=True)
    import yaml
    for name in [ROOT / ".github/workflows/server-pages-publish.yml", ROOT / "packaging/pages-repository/.github/workflows/pages.yml"]:
        assert isinstance(yaml.safe_load(name.read_text()), dict)
