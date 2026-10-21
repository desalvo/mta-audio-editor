from pathlib import Path
import sys
import pytest
from app import mega53_runtime
from app.model_license_policy import selected
from app.ai_backend_models import LEAD_BACKING_MODELS


def test_catalog_and_policy_identity():
    assert any(m['id'] == 'mvsep-mega53' for m in LEAD_BACKING_MODELS)
    assert selected('backing-vocals', {'model':'mvsep-mega53'}) == 'mvsep-mega53'
    assert selected('backing-vocals', {}) == 'mvsep-mega53'
    assert selected('backing-vocals', {'model':'uvr_mdxnet_kara_2'}) == 'uvr-kara-2'


def test_not_configured_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr('app.model_license_policy.evaluate_model', lambda x: None)
    monkeypatch.delenv('MTA_MEGA53_ROOT', raising=False)
    with pytest.raises(RuntimeError, match='upstream'):
        mega53_runtime.infer(tmp_path / 'input.wav', tmp_path / 'out')


def test_adapter_with_synthetic_stub(tmp_path, monkeypatch):
    """Contract-only test; no real checkpoint or quality measurement."""
    monkeypatch.setattr('app.model_license_policy.evaluate_model', lambda x: None)
    root=tmp_path/'upstream';root.mkdir()
    (root/'inference.py').write_text('''import argparse\nfrom pathlib import Path\np=argparse.ArgumentParser()\nfor k in ("model_type", "config_path", "start_check_point", "input_folder", "store_dir"):p.add_argument("--"+k)\na=p.parse_args()\nout=Path(a.store_dir);out.mkdir(parents=True,exist_ok=True)\n(out/"mta_input_lead-vocal.wav").write_bytes(b"RIFFlead")\n(out/"mta_input_back-vocal.wav").write_bytes(b"RIFFback")\n''')
    config=tmp_path/'config.yaml'; config.write_text('config')
    ckpt=tmp_path/'weight.ckpt'; ckpt.write_bytes(b'checkpoint')
    source=tmp_path/'song.wav';source.write_bytes(b'RIFFsong')
    for key,value in [('MTA_MEGA53_ROOT',root),('MTA_MEGA53_CONFIG',config),('MTA_MEGA53_CHECKPOINT',ckpt),('MTA_MEGA53_PYTHON',Path(sys.executable).resolve())]:monkeypatch.setenv(key,str(value))
    monkeypatch.setattr(mega53_runtime, 'verify_mega53_checkpoint', lambda value: Path(value))
    lead,backing,engine=mega53_runtime.infer(source,tmp_path/'output')
    assert lead.read_bytes()==b'RIFFlead' and backing.read_bytes()==b'RIFFback'
    assert engine=='mvsep-mega53'


def test_invalid_model_files_are_rejected(tmp_path,monkeypatch):
    monkeypatch.setattr('app.model_license_policy.evaluate_model', lambda x: None)
    root=tmp_path/'upstream';root.mkdir();(root/'inference.py').write_text('')
    source=tmp_path/'x.wav';source.write_bytes(b'x')
    monkeypatch.setenv('MTA_MEGA53_ROOT',str(root))
    monkeypatch.setenv('MTA_MEGA53_CONFIG',str(tmp_path/'missing.yml'))
    with pytest.raises(RuntimeError,match='config'):
        mega53_runtime.infer(source,tmp_path/'output')
