"""The removed individual-singer workflow cannot execute through legacy payloads."""
import pytest
from app import main,ai_unified_adapter,model_selectors

def test_individual_singer_helpers_are_absent():
    for name in ('_parse_singers_json','_extract_singer_stems','_SINGER_MODEL_IDS'):
        assert not hasattr(main,name)

@pytest.mark.parametrize('target',['all','singer_1','singer_2'])
def test_retired_singer_target_is_rejected_before_output(tmp_path,target):
    plan={'kind':'singer-separation','selected':target}
    with pytest.raises(ValueError,match='removed'):model_selectors.validate_selection('singer-separation',plan)
    output=tmp_path/'missing'/'out.wav'
    with pytest.raises(ValueError,match='Unsupported'):ai_unified_adapter.infer(plan,output)
    assert not output.parent.exists()
