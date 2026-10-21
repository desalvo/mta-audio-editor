import hashlib
import json
import pytest
from scripts.check_neural_validation_assets import inspect


def bundle(tmp_path):
    (tmp_path/'asset.bin').write_bytes(b'asset')
    item={'path':'asset.bin','bytes':5,'sha256':hashlib.sha256(b'asset').hexdigest()}
    (tmp_path/'ASSET_MANIFEST.json').write_text(json.dumps({'files':[item]}))
    return item


def test_audit_does_not_authorize_or_infer(tmp_path):
    bundle(tmp_path);result=inspect(tmp_path)
    assert len(result['verified'])==1
    assert result['inference_executed'] is False and result['licenses_approved'] is False


def test_tampered_asset_is_rejected(tmp_path):
    bundle(tmp_path);(tmp_path/'asset.bin').write_bytes(b'other')
    with pytest.raises(ValueError,match='integrity'):inspect(tmp_path)


def test_parent_escape_is_rejected(tmp_path):
    item=bundle(tmp_path);item['path']='../asset.bin'
    (tmp_path/'ASSET_MANIFEST.json').write_text(json.dumps({'files':[item]}))
    with pytest.raises(ValueError,match='Unsafe'):inspect(tmp_path)
