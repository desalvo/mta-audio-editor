import pytest
from app.vocal_conversion import validate_seed_config


@pytest.mark.parametrize('rate,dit,reg',[(22050,False,False),(44100,False,True),(44100,True,False)])
def test_speech_or_mixed_architecture_is_rejected(tmp_path,rate,dit,reg):
    import yaml
    p=tmp_path/'config.yml'
    p.write_text(yaml.safe_dump({'preprocess_params':{'sr':rate},'model_params':{
        'DiT':{'f0_condition':dit},'length_regulator':{'f0_condition':reg}}}))
    with pytest.raises(ValueError,match='F0-conditioned'):validate_seed_config(p)


def test_missing_architecture_is_rejected(tmp_path):
    p=tmp_path/'config.yml';p.write_text('{}')
    with pytest.raises(ValueError,match='F0-conditioned'):validate_seed_config(p)
