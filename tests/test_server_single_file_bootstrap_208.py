"""Regression tests for downloading only install_mta.sh."""
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_local_native_helpers_work_without_network():
    p = subprocess.run(['bash', str(ROOT/'scripts/install_mta.sh'), '--native-server', 'early', '--dry-run'], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    assert 'NATIVE_SERVER channel=early' in p.stdout


def test_single_file_native_bootstrap(tmp_path):
    script = tmp_path/'install_mta.sh'
    shutil.copyfile(ROOT/'scripts/install_mta.sh', script)
    bindir = tmp_path/'bin'
    bindir.mkdir()
    curl = bindir/'curl'
    curl.write_text('''#!/usr/bin/env bash
set -e
url=''; out=''
while (($#)); do
  case "$1" in -o) shift; out="$1";; https://*) url="$1";; esac
  shift
done
case "$url" in
 */install_mta_native.sh) cp "$MTA_FIXTURE_ROOT/scripts/install_mta_native.sh" "$out";;
 */repositories/install_repository.sh) cp "$MTA_FIXTURE_ROOT/scripts/repositories/install_repository.sh" "$out";;
 *) exit 7;;
esac
''')
    curl.chmod(0o755)
    env = dict(os.environ, PATH=str(bindir) + os.pathsep + os.environ['PATH'],
               MTA_INSTALL_REF='a'*40, MTA_FIXTURE_ROOT=str(ROOT))
    p = subprocess.run(['bash', str(script), '--native-server', 'early', '--dry-run'], capture_output=True, text=True, env=env)
    assert p.returncode == 0, p.stderr
    assert 'NATIVE_SERVER channel=early' in p.stdout


def test_invalid_pinned_sha_fails_closed(tmp_path):
    script = tmp_path/'install_mta.sh'
    shutil.copyfile(ROOT/'scripts/install_mta.sh', script)
    env = dict(os.environ, MTA_INSTALL_REF='main')
    p = subprocess.run(['bash', str(script), '--native-server', 'early', '--dry-run'], capture_output=True, text=True, env=env)
    assert p.returncode == 2
    assert 'Invalid MTA_INSTALL_REF' in p.stderr


def test_downloaded_repository_helper_is_executable(tmp_path):
    """Bootstrap must support the native installer's nested exec."""
    script = tmp_path / 'install_mta.sh'
    shutil.copyfile(ROOT / 'scripts/install_mta.sh', script)
    fixture = tmp_path / 'fixture'
    (fixture / 'repositories').mkdir(parents=True)
    (fixture / 'install_mta_native.sh').write_text(
        '#!/usr/bin/env bash\nset -e\nexec "$(dirname "${BASH_SOURCE[0]}")/repositories/install_repository.sh" "$@"\n'
    )
    (fixture / 'repositories/install_repository.sh').write_text(
        '#!/usr/bin/env bash\nprintf "EXECUTED_HELPER %s\\n" "$*"\n'
    )
    bindir = tmp_path / 'bin'
    bindir.mkdir()
    curl = bindir / 'curl'
    curl.write_text("""#!/usr/bin/env bash
set -e
url=''; out=''
while (($#)); do
  case "$1" in -o) shift; out="$1";; https://*) url="$1";; esac
  shift
done
case "$url" in
 */install_mta_native.sh) cp "$MTA_FIXTURE_ROOT/install_mta_native.sh" "$out";;
 */repositories/install_repository.sh) cp "$MTA_FIXTURE_ROOT/repositories/install_repository.sh" "$out";;
 *) exit 7;;
esac
""")
    curl.chmod(0o755)
    env = dict(os.environ, PATH=str(bindir) + os.pathsep + os.environ['PATH'],
               MTA_INSTALL_REF='a' * 40, MTA_FIXTURE_ROOT=str(fixture))
    result = subprocess.run(['bash', str(script), '--native-server', 'early'],
                            capture_output=True, text=True, env=env)
    assert result.returncode == 0, result.stderr
    assert 'EXECUTED_HELPER early' in result.stdout
