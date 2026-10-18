#!/usr/bin/env python3
"""Build an isolated, source-pinned AMD-SMI; never install a driver or switch MTA."""
import argparse
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile

REPOSITORY = "https://github.com/ROCm/rocm-systems.git"
TAG = "rocm-7.2.4"
COMMIT = "97f5574fe2fdc7bef44fb01545347912ee9f1779"
ESMI_REPOSITORY = "https://github.com/amd/esmi_ib_library.git"
ESMI_TAG = "esmi_pkg_ver-4.2"
ESMI_COMMIT = "fae8e8e7af086bcf974d406bbac0c6e1ed1a25f9"
DEFAULT_PREFIX = "/opt/mta-amdsmi/rocm-7.2.4"
PYTHON = "/usr/bin/python3"
MARKER = "mta-amdsmi-sidecar-v1"
DEPS = "apt-get install --no-install-recommends git build-essential cmake pkg-config libdrm-dev python3"

# -I excludes cwd, user site and PYTHONPATH. Both bindings and shared library
# come from this prefix; reject fallback to Debian's older shared library.
LAUNCHER = '''from pathlib import Path
import json
import os
import runpy
import sys
root = Path(__file__).resolve().parents[1]
os.environ["ROCM_HOME"] = os.environ["ROCM_PATH"] = str(root)
sys.path[:0] = [str(root / "share/amd_smi"), str(root / "libexec/amdsmi_cli")]
from amdsmi import amdsmi_wrapper
loaded = Path(amdsmi_wrapper.location).resolve()
expected = (root / "lib/libamd_smi.so").resolve()
if loaded != expected:
    raise SystemExit("Refusing unexpected AMD-SMI library: " + str(loaded))
if sys.argv[1:] == ["--mta-library-info"]:
    print(json.dumps({"library": str(loaded), "source_commit": "@COMMIT@",
                      "billing_eligible": False}))
else:
    runpy.run_path(str(root / "libexec/amdsmi_cli/amdsmi_cli.py"), run_name="__main__")
'''.replace("@COMMIT@", COMMIT)


def run(args, **kwargs):
    print("+ " + shlex.join(map(str, args)), flush=True)
    return subprocess.run(list(map(str, args)), check=True, **kwargs)


def validate_prefix(value):
    path = Path(value).expanduser()
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("Prefix must be an absolute path without '..'")
    # Only a dedicated child under /opt/mta-amdsmi is accepted on the host.
    # Refuse symlink ancestors as well as an existing destination.
    if path.parent != Path("/opt/mta-amdsmi") or path.name.startswith("."):
        raise ValueError("Prefix must be a direct child of /opt/mta-amdsmi")
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("Prefix and ancestors must not be symlinks")
    return path


def preflight():
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise RuntimeError("Run this tool on the x86_64 Linux Proxmox host (gwads07)")
    if not Path("/etc/pve").is_dir():
        raise RuntimeError("/etc/pve absent: run on the Proxmox host, not inside LXC")
    for command in ("git", "cmake", "pkg-config", "g++", "make", "objdump"):
        if not shutil.which(command):
            raise RuntimeError(f"Missing {command}. Build prerequisites: {DEPS}")
    run(["pkg-config", "--exists", "libdrm", "libdrm_amdgpu"])
    run([PYTHON, "-I", "-c", "import ctypes"])
    version = subprocess.check_output(["cmake", "--version"], text=True).split()[2]
    if tuple(int(n) for n in version.split(".")[:2]) < (3, 20):
        raise RuntimeError("CMake >= 3.20 required")


def build_commands(source, build, prefix, jobs):
    return [
        ["cmake", "-S", str(source / "projects/amdsmi"), "-B", str(build),
         "-DCMAKE_BUILD_TYPE=Release", f"-DCMAKE_INSTALL_PREFIX={prefix}",
         "-DENABLE_ESMI_LIB=ON", "-DENABLE_LDCONFIG=OFF", "-DBUILD_WRAPPER=OFF",
         "-DBUILD_TESTS=OFF", "-DBUILD_EXAMPLES=OFF", "-DBUILD_CLI=ON"],
        ["cmake", "--build", str(build), "--target", "amdsmi_cli", "--parallel", str(jobs)],
    ]


def stage_build(build, stage):
    bindings = build / "py-interface/python_package/amdsmi"
    cli = build / "amdsmi_cli/amdsmi_cli"
    library = bindings / "libamd_smi.so"
    if not library.is_file() or not (cli / "amdsmi_cli.py").is_file():
        raise RuntimeError("Expected AMD-SMI build outputs are missing")
    (stage / "share/amd_smi").mkdir(parents=True)
    shutil.copytree(bindings, stage / "share/amd_smi/amdsmi", symlinks=False)
    shutil.copytree(cli, stage / "libexec/amdsmi_cli", symlinks=False)
    (stage / "lib").mkdir()
    shutil.copy2(library, stage / "lib/libamd_smi.so")
    # First upstream lookup is <prefix>/lib/libamd_smi.so.26. A matching
    # Python ABI and this alias prevent fallback to the system SMI library.
    (stage / "lib/libamd_smi.so.26").symlink_to("libamd_smi.so")
    (stage / "bin").mkdir()
    (stage / "bin/launcher.py").write_text(LAUNCHER, encoding="utf-8")
    (stage / "bin/amd-smi").write_text(
        '#!/bin/sh\nexec /usr/bin/python3 -I "$(dirname -- "$0")/launcher.py" "$@"\n',
        encoding="utf-8",
    )
    (stage / "bin/amd-smi").chmod(0o755)
    (stage / "manifest.json").write_text(json.dumps({
        "marker": MARKER, "repository": REPOSITORY, "tag": TAG,
        "commit": COMMIT, "esmi_commit": ESMI_COMMIT, "billing_eligible": False,
    }, indent=2) + "\n", encoding="utf-8")


def install(prefix, jobs):
    if prefix.exists():
        raise RuntimeError(f"Destination already exists; left unchanged: {prefix}")
    prefix.parent.mkdir(parents=True, exist_ok=True)
    parent_stat = prefix.parent.stat()
    if parent_stat.st_uid != 0 or parent_stat.st_mode & 0o022:
        raise RuntimeError("Installation parent must be root-owned and not group/world writable")
    # Private same-filesystem staging allows atomic publication only after
    # build and library-origin verification. No cmake --install / ldconfig.
    with tempfile.TemporaryDirectory(prefix=".build-", dir=prefix.parent) as temporary:
        work = Path(temporary)
        source, build, stage = work / "source", work / "build", work / "stage"
        run(["git", "clone", "--filter=blob:none", "--depth", "1", "--sparse",
             "--branch", TAG, REPOSITORY, source])
        actual = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
        if actual != COMMIT:
            raise RuntimeError("Upstream tag does not match the pinned commit; refusing build")
        run(["git", "-C", source, "sparse-checkout", "set", "projects/amdsmi"])
        # The shipped ctypes wrapper also references CPU symbols. Build the
        # matching userspace component, without installing/loading HSMP/DKMS.
        esmi = source / "projects/amdsmi/esmi_ib_library"
        run(["git", "clone", "--depth", "1", "--branch", ESMI_TAG, ESMI_REPOSITORY, esmi])
        actual_esmi = subprocess.check_output(["git", "-C", str(esmi), "rev-parse", "HEAD"], text=True).strip()
        if actual_esmi != ESMI_COMMIT:
            raise RuntimeError("ESMI tag does not match the pinned commit; refusing build")
        for command in build_commands(source, build, prefix, jobs):
            run(command)
        if subprocess.check_output(["git", "-C", str(esmi), "rev-parse", "HEAD"], text=True).strip() != ESMI_COMMIT:
            raise RuntimeError("ESMI source changed during configure; refusing publication")
        stage_build(build, stage)
        shutil.copy2(source / "projects/amdsmi/LICENSE", stage / "LICENSE-AMD-SMI")
        shutil.copy2(esmi / "License.txt", stage / "LICENSE-ESMI")
        run([stage / "bin/amd-smi", "--mta-library-info"])
        # Refuse a concurrently created destination rather than merge/replace.
        # The parent is root-owned; simultaneous installs are unsupported.
        if prefix.exists():
            raise RuntimeError("Destination appeared during build; refusing overwrite")
        stage.rename(prefix)
    print(f"Installed isolated AMD-SMI: {prefix}/bin/amd-smi")
    print("Debian AMD-SMI, drivers, kernel and MTA agent configuration remain unchanged.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    parser.add_argument("--jobs", type=int, default=2, help="Build parallelism (default: 2)")
    parser.add_argument("--install", action="store_true", help="Build and publish the isolated tools")
    args = parser.parse_args(argv)
    try:
        prefix = validate_prefix(args.prefix)
        if not 1 <= args.jobs <= 32:
            raise ValueError("--jobs must be between 1 and 32")
        preflight()
        if args.install:
            if os.geteuid() != 0:
                raise RuntimeError("--install requires root on the Proxmox host")
            install(prefix, args.jobs)
        else:
            print(f"Preflight passed. No changes made. Use --install to build {TAG} at {prefix}.")
    except (ValueError, RuntimeError, OSError, subprocess.CalledProcessError) as error:
        print(f"AMD-SMI sidecar: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
