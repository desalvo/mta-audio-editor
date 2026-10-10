from types import SimpleNamespace
from unittest.mock import patch
import pytest
from app.vst3_host import apply_parameters


class Param:
    def __init__(self, value):
        self.raw_value = value


def test_vst3_normalized_parameters_are_applied():
    plugin = SimpleNamespace(parameters={'mix': Param(0.5), 'depth': Param(0.25)})
    apply_parameters(plugin, {'mix': 0.8, 'depth': 0})
    assert plugin.parameters['mix'].raw_value == 0.8
    assert plugin.parameters['depth'].raw_value == 0.0


def test_vst3_invalid_parameter_does_not_silently_pass():
    plugin = SimpleNamespace(parameters={'mix': Param(0.5)})
    with pytest.raises(ValueError, match='unavailable'):
        apply_parameters(plugin, {'missing': 0.8})
    with pytest.raises(ValueError, match='outside'):
        apply_parameters(plugin, {'mix': 1.5})
