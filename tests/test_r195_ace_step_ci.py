from pathlib import Path
import pytest
from scripts.verify_ace_step_bundle import verify


def _make_source(tmp_path: Path) -> Path:
    root = tmp_path / "ace-step-1.5"
    (root / "acestep").mkdir(parents=True)
    (root / "UPSTREAM_COMMIT").write_text("a" * 40)
    (root / "LICENSE").write_text("MIT License\nPermission is hereby granted, free of charge")
    (root / "pyproject.toml").write_text("[project]\nname='ace-step'")
    return root


def test_valid_source_snapshot(tmp_path):
    assert verify(_make_source(tmp_path)) == "a" * 40


def test_reject_checkpoint(tmp_path):
    root = _make_source(tmp_path)
    (root / "model.safetensors").write_bytes(b"x")
    with pytest.raises(ValueError, match="checkpoint"):
        verify(root)


def test_reject_invalid_sha(tmp_path):
    root = _make_source(tmp_path)
    (root / "UPSTREAM_COMMIT").write_text("main")
    with pytest.raises(ValueError, match="commit"):
        verify(root)


def test_reject_missing_license(tmp_path):
    root = _make_source(tmp_path)
    (root / "LICENSE").unlink()
    with pytest.raises(FileNotFoundError):
        verify(root)


def test_workflow_manual_pinned_checkout_and_artifact():
    p = Path(__file__).resolve().parents[1] / '.github/workflows/ace-step-bundle.yml'
    data = p.read_text()
    assert 'workflow_dispatch:' in data
    assert 'inputs.upstream_commit' in data
    assert 'scripts/resolve_ace_step_version.py' in data
    assert 'steps.release.outputs.commit' in data
    assert 'vendor_ace_step.sh' in data
    assert 'verify_ace_step_bundle.py' in data
    assert 'actions/upload-artifact@v4' in data


def test_default_ace_step_stable_release():
    from scripts.resolve_ace_step_version import load_tag, parse_refs
    assert load_tag() == 'v0.1.8'
    assert parse_refs('a' * 40 + '\trefs/tags/v0.1.8\n', 'v0.1.8') == 'a' * 40
    assert parse_refs('a' * 40 + '\trefs/tags/v0.1.8\n' + 'b' * 40 + '\trefs/tags/v0.1.8^{}\n', 'v0.1.8') == 'b' * 40


def test_ace_step_automated_update_requires_pull_request():
    p = Path(__file__).resolve().parents[1] / '.github/workflows/ace-step-update.yml'
    data = p.read_text()
    assert 'schedule:' in data
    assert '/releases/latest' in data
    assert 'peter-evans/create-pull-request@v7' in data
    assert 'ace_step_version.json' in data
