from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from app.chordino_runtime import chordino_status, clear_chordino_probe_cache, host_kind


def test_chordino_runtime_accepts_sonic_annotator_and_checks_plugin(tmp_path):
    host = tmp_path / ("sonic-annotator.exe" if os.name == "nt" else "sonic-annotator")
    host.write_text("x")
    clear_chordino_probe_cache()
    with patch.dict(os.environ, {"MTA_CHORDINO_HOST": str(host), "MTA_VAMP_PATH": str(tmp_path)}), patch(
        "app.chordino_runtime.subprocess.run"
    ) as run:
        run.return_value.returncode = 0
        run.return_value.stdout = "vamp:nnls-chroma:chordino:simplechord\n"
        run.return_value.stderr = ""
        status = chordino_status()
    clear_chordino_probe_cache()
    assert status["available"] is True
    assert status["plugin"] is True
    assert status["host_kind"] == "sonic-annotator"
    assert host_kind(str(host)) == "sonic-annotator"


def test_chordino_runtime_accepts_vamp_simple_host(tmp_path):
    host = tmp_path / "vamp-simple-host"
    host.write_text("x")
    clear_chordino_probe_cache()
    with patch.dict(os.environ, {"MTA_CHORDINO_HOST": str(host)}), patch(
        "app.chordino_runtime.subprocess.run"
    ) as run:
        run.return_value.returncode = 0
        run.return_value.stdout = "vamp:nnls-chroma:chordino\n"
        run.return_value.stderr = ""
        status = chordino_status()
        assert run.call_args.args[0][-1] == "--list-ids"
    clear_chordino_probe_cache()
    assert status["available"] is True
    assert status["host_kind"] == "vamp-simple-host"


def test_packaging_bundles_chordino_for_container_and_native():
    docker = Path("Dockerfile").read_text()
    workflow = Path(".github/workflows/ci-cd.yml").read_text()
    spec = Path("native/mta_audio_editor_native.spec").read_text()
    launcher = Path("native/mta_audio_editor_native.py").read_text()
    windows = Path("scripts/provision_chordino_windows.ps1").read_text()
    unix = Path("scripts/build_chordino_unix.sh").read_text()
    assert "vamp-examples" in docker
    assert "Makefile.linux" in docker and "nnls-chroma:chordino" in docker
    assert "Provision bundled Chordino runtime" in workflow
    assert "MTA_NATIVE_CHORDINO_BIN_DIR" in workflow and "MTA_NATIVE_CHORDINO_VAMP_DIR" in workflow
    assert '"vamp"' in spec and "MTA_NATIVE_CHORDINO_VAMP_DIR" in spec
    assert "configure_chordino_environment" in launcher
    assert "sonic-annotator" in windows and "PrebuiltPlugin" in windows
    assert "nnls-chroma-win64" in workflow and "chordino-windows-x64-runtime" in workflow
    assert "Makefile.osx" in unix and "vamp-simple-host" in unix
