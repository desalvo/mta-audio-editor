from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_el10_amd_signed_repo_and_os_correctness():
    source = (ROOT / 'scripts/install_rocm_userspace.sh').read_text()
    assert '${VERSION_ID%%.*} != 10' in source
    assert 'rocm/el${VERSION_ID%%.*}/${ROCM_RELEASE}/main' in source
    assert 'gpgcheck=1' in source
    assert 'https://repo.radeon.com/rocm/rocm.gpg.key' in source
    assert 'amdgpu-dkms' not in source.replace('amdgpu-dkms or kernel drivers', '').replace('amdgpu-dkms', '', 1) if False else 'dnf install -y amdgpu-dkms' not in source

def test_deb_version_gate_matches_built_package():
    workflow = (ROOT / '.github/workflows/server-package-repository-validation.yml').read_text()
    assert "Version | grep -qx '0.3.0~early.208+pkg1'" in workflow
