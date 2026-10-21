"""Do not accidentally charge Mega 53 against blocked DrumSep checkpoint rights."""
from unittest.mock import patch
import pytest
from app.model_license_policy import selected, evaluate, LicenseDenied


def test_remote_drum_models_select_correct_license():
    assert selected('drumsep', {'model':'mvsep-mega53'}) == 'mvsep-mega53'
    assert selected('drumsep', {'model':'dsp'}) == 'mta-analysis'
    assert selected('drumsep', {'model':'drumsep-onnx'}) == 'drumsep-weights'
    assert selected('drumsep', {'model':'sam-audio-base'}) == 'sam-audio'


def test_default_neural_weights_remain_blocked():
    with patch('app.model_license_policy.overrides', return_value={}):
        with pytest.raises(LicenseDenied):
            evaluate('drumsep', {'model':'drumsep-onnx'})
        assert evaluate('drumsep', {'model':'mvsep-mega53'}).model_id == 'mvsep-mega53'
