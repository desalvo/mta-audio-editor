from pathlib import Path
from unittest.mock import patch
from app import mega53_runtime as m

def test_two_native_group_sources_requested_from_original_mix():
    paths = [Path('/tmp/drums_without_percussions.wav'), Path('/tmp/percussions.wav')]
    with patch.object(m, 'infer', return_value=paths) as run:
        assert m.infer_drums_vs_percussion('/tmp/original_mix.wav', '/tmp/output') == tuple(paths)
    assert run.call_args.args[0] == '/tmp/original_mix.wav'
    assert run.call_args.kwargs['drum_targets'] == {'drums', 'percussion'}

def test_missing_group_stem_is_rejected():
    import pytest
    with patch.object(m,'infer',return_value=[Path('/tmp/percussions.wav')]):
        with pytest.raises(RuntimeError,match='both drums and percussion'):
            m.infer_drums_vs_percussion('source','out')
