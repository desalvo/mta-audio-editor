import importlib.util
import json
import os
from pathlib import Path
import subprocess

import pytest


spec = importlib.util.spec_from_file_location(
    "amdsmi_sidecar", Path(__file__).resolve().parents[1] / "scripts/install_amdsmi_sidecar.py"
)
sidecar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sidecar)


@pytest.fixture
def install_parent_metadata(monkeypatch, tmp_path):
    """Model host parent ownership without requiring root or changing the OS."""
    real_stat = Path.stat

    def configure(uid=0, mode=0o700):
        def stat(path, *args, **kwargs):
            actual = real_stat(path, *args, **kwargs)
            if path == tmp_path:
                fields = list(actual)
                fields[0] = (actual.st_mode & ~0o777) | mode
                fields[4] = uid
                return os.stat_result(fields)
            return actual

        monkeypatch.setattr(Path, "stat", stat)

    return configure


@pytest.mark.parametrize("prefix", ["/", "/opt", "/usr/bin", "relative", "/opt/mta-amdsmi/../bad",
                                     "/opt/mta-amdsmi", "/opt/mta-amdsmi/.hidden", "/var/rocm"])
def test_reject_unsafe_prefix(prefix):
    with pytest.raises(ValueError):
        sidecar.validate_prefix(prefix)


def test_prefix_and_symlink_rejection(monkeypatch):
    assert sidecar.validate_prefix(sidecar.DEFAULT_PREFIX) == Path(sidecar.DEFAULT_PREFIX)
    monkeypatch.setattr(Path, "is_symlink", lambda p: str(p) == "/opt/mta-amdsmi")
    with pytest.raises(ValueError, match="symlinks"):
        sidecar.validate_prefix(sidecar.DEFAULT_PREFIX)


def test_build_commands_do_not_install_or_generate_global_bindings(tmp_path):
    commands = sidecar.build_commands(tmp_path / "source", tmp_path / "build", tmp_path / "stage", 2)
    assert "-DENABLE_ESMI_LIB=ON" in commands[0]
    assert "-DENABLE_LDCONFIG=OFF" in commands[0]
    assert "-DBUILD_WRAPPER=OFF" in commands[0]
    assert "amdsmi_cli" in commands[1]
    assert all("--install" not in cmd for cmd in commands)


def fake_build(tmp_path, wrapper):
    build = tmp_path / "build"
    bindings = build / "py-interface/python_package/amdsmi"
    bindings.mkdir(parents=True)
    (bindings / "__init__.py").write_text("")
    (bindings / "amdsmi_wrapper.py").write_text(wrapper)
    (bindings / "libamd_smi.so").write_bytes(b"fake-build-library")
    cli = build / "amdsmi_cli/amdsmi_cli"
    cli.mkdir(parents=True)
    (cli / "amdsmi_cli.py").write_text("print('cli executed')")
    return build


def test_launcher_uses_private_modules_and_library_despite_pythonpath(tmp_path):
    build = fake_build(tmp_path, 'from pathlib import Path\nlocation = Path(__file__).resolve().parents[3] / "lib/libamd_smi.so"\n')
    stage = tmp_path / "staging path with spaces"
    sidecar.stage_build(build, stage)
    assert json.loads((stage / "manifest.json").read_text())["billing_eligible"] is False
    assert (stage / "lib/libamd_smi.so.26").resolve() == stage / "lib/libamd_smi.so"
    poison = tmp_path / "poison"
    poison.mkdir()
    (poison / "amdsmi.py").write_text("raise RuntimeError('incorrect system bindings')")
    import os
    env = dict(os.environ, PYTHONPATH=str(poison), ROCM_HOME="/incorrect", ROCM_PATH="/incorrect")
    result = subprocess.run([str(stage / "bin/amd-smi"), "--mta-library-info"],
                            env=env, cwd=poison, capture_output=True, text=True, check=True)
    info = json.loads(result.stdout)
    assert info["library"] == str(stage / "lib/libamd_smi.so")
    assert info["source_commit"] == sidecar.COMMIT
    result = subprocess.run([str(stage / "bin/amd-smi"), "version"],
                            env=env, capture_output=True, text=True, check=True)
    assert "cli executed" in result.stdout


def test_launcher_refuses_fallback_system_library(tmp_path):
    build = fake_build(tmp_path, 'location = "/usr/lib/libamd_smi.so"\n')
    stage = tmp_path / "stage"
    sidecar.stage_build(build, stage)
    result = subprocess.run([str(stage / "bin/amd-smi"), "version"], capture_output=True, text=True)
    assert result.returncode != 0
    assert "Refusing unexpected" in result.stderr
    assert "cli executed" not in result.stdout


def test_missing_build_outputs_not_published(tmp_path):
    with pytest.raises(RuntimeError, match="missing"):
        sidecar.stage_build(tmp_path / "absent", tmp_path / "stage")
    assert not (tmp_path / "stage").exists()


def test_existing_destination_not_overwritten(tmp_path):
    with pytest.raises(RuntimeError, match="already exists"):
        sidecar.install(tmp_path, 2)


def test_preflight_and_install_require_explicit_flag(monkeypatch):
    calls = []
    monkeypatch.setattr(sidecar, "preflight", lambda: calls.append("check"))
    monkeypatch.setattr(sidecar, "install", lambda *args: calls.append("install"))
    monkeypatch.setattr(sidecar.os, "geteuid", lambda: 0)
    assert sidecar.main([]) == 0
    assert calls == ["check"]
    assert sidecar.main(["--install"]) == 0
    assert calls == ["check", "check", "install"]


def test_failure_returns_error(monkeypatch, capsys):
    def failure():
        raise RuntimeError("missing dependency")
    monkeypatch.setattr(sidecar, "preflight", failure)
    assert sidecar.main([]) == 1
    assert "missing dependency" in capsys.readouterr().err


@pytest.mark.parametrize("jobs", ["0", "33", "-1"])
def test_invalid_parallelism(jobs):
    assert sidecar.main(["--jobs", jobs]) == 1


def test_wrong_host_rejected(monkeypatch):
    monkeypatch.setattr(sidecar.platform, "system", lambda: "Linux")
    monkeypatch.setattr(sidecar.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(Path, "is_dir", lambda path: False)
    with pytest.raises(RuntimeError, match="not inside LXC"):
        sidecar.preflight()


def test_tag_mismatch_is_not_built_and_cleans_staging(monkeypatch, tmp_path, install_parent_metadata):
    install_parent_metadata()
    prefix = tmp_path / "new"
    calls = []
    monkeypatch.setattr(sidecar, "run", lambda args, **kwargs: calls.append(args))
    monkeypatch.setattr(sidecar.subprocess, "check_output", lambda *args, **kwargs: "wrong\n")
    with pytest.raises(RuntimeError, match="pinned commit"):
        sidecar.install(prefix, 2)
    assert len(calls) == 1 and calls[0][0:2] == ["git", "clone"]
    assert not prefix.exists()
    assert not list(tmp_path.glob(".build-*"))


@pytest.mark.parametrize("load_fails", [False, True])
def test_publish_only_after_private_library_verification(monkeypatch, tmp_path, load_fails, install_parent_metadata):
    install_parent_metadata()
    prefix = tmp_path / "published"
    monkeypatch.setattr(sidecar.subprocess, "check_output", lambda args, **kwargs:
                        (sidecar.ESMI_COMMIT if "esmi_ib_library" in args[2] else sidecar.COMMIT) + "\n")
    seen = []

    def simulate(args, **kwargs):
        seen.append(args)
        if args[0:2] == ["git", "clone"]:
            license = Path(args[-1]) / ("License.txt" if args[-2] == sidecar.ESMI_REPOSITORY else "projects/amdsmi/LICENSE")
            license.parent.mkdir(parents=True)
            license.write_text("upstream license")
        if args[0:2] == ["cmake", "--build"]:
            fake_build(Path(args[2]).parent, 'location = "unused"\n')
        if str(args[0]).endswith("/bin/amd-smi"):
            assert not prefix.exists()
            if load_fails:
                raise subprocess.CalledProcessError(1, args)

    monkeypatch.setattr(sidecar, "run", simulate)
    if load_fails:
        with pytest.raises(subprocess.CalledProcessError):
            sidecar.install(prefix, 2)
        assert not prefix.exists()
    else:
        sidecar.install(prefix, 2)
        assert (prefix / "bin/amd-smi").is_file()
        assert (prefix / "LICENSE-AMD-SMI").read_text() == "upstream license"
        assert json.loads((prefix / "manifest.json").read_text())["commit"] == sidecar.COMMIT
    assert seen[-1][1] == "--mta-library-info"
    assert not list(tmp_path.glob(".build-*"))


@pytest.mark.parametrize("uid,mode", [(1000, 0o700), (1000, 0o755), (0, 0o770), (0, 0o707), (0, 0o777)])
def test_untrusted_parent_is_rejected_before_clone(monkeypatch, tmp_path, install_parent_metadata, uid, mode):
    install_parent_metadata(uid, mode)
    calls = []
    monkeypatch.setattr(sidecar, "run", lambda args, **kwargs: calls.append(args))
    with pytest.raises(RuntimeError, match="root-owned and not group/world writable"):
        sidecar.install(tmp_path / "unpublished", 2)
    assert calls == []
    assert list(tmp_path.iterdir()) == []


def test_non_root_install_requires_privileges_before_mutation(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(sidecar, "preflight", lambda: None)
    monkeypatch.setattr(sidecar.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(sidecar, "install", lambda *args: calls.append(args))
    assert sidecar.main(["--install"]) == 1
    assert "requires root" in capsys.readouterr().err
    assert calls == []
