from pathlib import Path
import pytest
from app import main, mega53_runtime
from app import model_license_policy as policy

def test_uvr_primary_and_mega_secondary():
    catalog=main._lead_backing_catalog()
    assert catalog['default_model']=='uvr_mdxnet_kara_2'
    assert catalog['models'][0]['id']=='mvsep-mega53' or any(x['id']=='mvsep-mega53' for x in catalog['models'])
    assert policy.CATALOG['uvr-kara-2'][1]=='disabled'
    assert policy.CATALOG['mvsep-mega53'][1]=='cost_recovery'

def test_mega53_rejects_unverified_weights(tmp_path):
    candidate=tmp_path/'fake.ckpt'
    candidate.write_bytes(b'not official Mega53')
    with pytest.raises(RuntimeError,match='SHA-256 mismatch'):
        mega53_runtime.verify_mega53_checkpoint(candidate)

def test_multi_singer_remains_distinct_from_lead_backing():
    source=Path(main.__file__).read_text()
    assert 'def _extract_singer_stems(' in source
    assert 'singer_model = str(job.get("singer_model") or "sam-audio-small")' in source
