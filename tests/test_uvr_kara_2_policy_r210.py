import pytest
from app import model_license_policy as license_policy
from app.uvr_kara_integrity import verify_kara_2, UVR_KARA_2_SHA256

def test_ownership_identity_is_separate():
    assert license_policy.selected('backing-vocals', {'model':'uvr_mdxnet_kara_2'}) == 'uvr-kara-2'
    assert license_policy.selected('backing-vocals', {'model':'mel_roformer_karaoke_gabox_v2'}) == 'audio-separator-weights'
    assert 'uvr-kara-2' in license_policy.RESTRICTED_MODELS
    assert license_policy.CATALOG['uvr-kara-2'][1] == 'disabled'

def test_fake_model_rejected(tmp_path):
    f=tmp_path/'UVR_MDXNET_KARA_2.onnx'; f.write_bytes(b'not the real checkpoint')
    with pytest.raises(ValueError,match='SHA-256'):
        verify_kara_2(f)
    assert len(UVR_KARA_2_SHA256)==64

def test_symlink_rejected(tmp_path):
    f=tmp_path/'real';f.write_bytes(b'test')
    alias=tmp_path/'alias';alias.symlink_to(f)
    with pytest.raises(ValueError,match='unsafe'):
        verify_kara_2(alias)
