"""Remote option tree is bounded identically for direct native and HTTP calls."""
import base64
import json
import math
import pytest
from app.ai_remote_transport import decode_audio_options, validate_audio_options
from app.ai_remote_client import infer_audio


def encode(obj):
    return base64.urlsafe_b64encode(json.dumps(obj, ensure_ascii=True).encode()).decode().rstrip('=')


INVALID = [
    {'source_audio': 'x'}, {'nested': {'source_audio': 'x'}},
    {'nested': {'input_path': 'x'}}, {'nested': {'output_path': 'x'}},
    {'nested': {'command': 'x'}}, {'nested': {'executable': 'x'}},
    {'nested': {'cwd': 'x'}}, {'nested': {'shell': 'x'}},
    {'a': [{'shell': 'ls'}]}, {'': 1}, {'a\\b': 1},
    {'a\nb': 1}, {'a\tb': 1}, {'a\x00b': 1},
    {'a\x7fb': 1}, {'x' * 81: 1},
    {'list': list(range(129))}, {'obj': {str(i): i for i in range(129)}},
    {'long': 'x' * 4097}, {'bad_surrogate': '\ud800'},
    {'deep': [[[[[[[[[1]]]]]]]]]},
    {'many': [[0 for i in range(128)] for j in range(5)]},
    {'float': float('nan')}, {'float': float('inf')},
    {'float': float('-inf')}, {'tuple': (1,2)}, {'set': {1,2}},
    {'bytes': b'hi'}, {'nested': {5: 1}},
]


@pytest.mark.parametrize('options', INVALID, ids=[f'boundary-{i+1}' for i in range(len(INVALID))])
def test_direct_options_invalid_before_network(options, monkeypatch):
    monkeypatch.setattr('app.ai_remote_client.https_urlopen', lambda *a, **k: pytest.fail('network used'))
    with pytest.raises((ValueError, TypeError)):
        infer_audio('https://example.org', 'token', 'whisper', b'RIFF', options=options)


@pytest.mark.parametrize('options', [v for i, v in enumerate(INVALID) if i not in (25, 28)], ids=[f'http-{i+1}' for i in range(len(INVALID)-2)])
def test_http_invalid_options(options):
    try:
        header = encode(options)
    except (TypeError, ValueError):
        return
    with pytest.raises(ValueError):
        decode_audio_options(header)


@pytest.mark.parametrize('raw', [
    '{"a":1,"a":2}', '{"a":{"b":1,"b":2}}',
    '{"a":NaN}', '{"a":Infinity}', '{"a":-Infinity}',
    '[1,2]', 'null', 'true',
])
def test_raw_duplicate_or_nonobject_or_nonfinite(raw):
    with pytest.raises(ValueError):
        decode_audio_options(base64.urlsafe_b64encode(raw.encode()).decode().rstrip('='))


def test_bounded_valid_nested_options_roundtrip():
    options = {'model': 'turbo', 'settings': {'temperature': 0.25, 'flags': [True, False, None]}, 'steps': 12}
    assert validate_audio_options(options) is options
    assert decode_audio_options(encode(options)) == options
