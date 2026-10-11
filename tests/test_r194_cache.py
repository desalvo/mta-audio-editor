from pathlib import Path
from app.ace_model_cache import cache_status


def test_cache_is_bounded_and_does_not_expose_paths(tmp_path: Path):
    a=tmp_path/'checkpoints'; a.mkdir()
    (a/'model.safetensors').write_bytes(b'weights')
    result=cache_status(roots=(a,))
    assert result['bytes_cached']==7 and result['file_count']==1
    assert result['inference_verified'] is False
    assert 'model.safetensors' not in str(result)
    assert str(tmp_path) not in str(result)
    assert cache_status(roots=(a,),file_limit=1)['file_count']==1


def test_empty_cache_not_ready(tmp_path: Path):
    result=cache_status(roots=(tmp_path/'missing',))
    assert not result['cache_available']
    assert result['models_ready'] is None
