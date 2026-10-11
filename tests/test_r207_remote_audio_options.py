import base64
import json
import pytest
from app.ai_remote_transport import decode_audio_options


def encode(value):
    return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip('=')


def test_audio_options_preserves_model_params():
    assert decode_audio_options(encode({'language':'it', 'model':'medium', 'stems':4})) == {'language':'it', 'model':'medium', 'stems':4}


@pytest.mark.parametrize('option', ['source_audio', 'input_path', 'output_path', 'command', 'executable', 'cwd', 'shell'])
def test_no_host_paths_or_executable(option):
    with pytest.raises(ValueError):
        decode_audio_options(encode({option:'/etc/passwd'}))


def test_bad_payloads_rejected():
    for bad in ['$$$', encode(['wrong']), encode({'language':'x'*10000})]:
        with pytest.raises(ValueError):
            decode_audio_options(bad)


def test_empty_header_uses_defaults():
    assert decode_audio_options('') == {}
