"""Retired profiled backend and native payloads cannot create runtime effects."""
from pathlib import Path
import pytest
from app import ai_unified_adapter as unified,ai_profiled_backend

@pytest.mark.parametrize('kind',['sam-audio','singer-separation'])
def test_removed_profile_backend_is_refused_before_profiler(tmp_path,monkeypatch,kind):
    monkeypatch.setattr(ai_profiled_backend,'profile_call',lambda *a,**k:pytest.fail('Removed backend profiled'))
    with pytest.raises(ValueError,match='Unsupported'):unified._backend_command({},tmp_path/'missing',kind,[])
    assert not (tmp_path/'missing').exists()

def test_native_payload_contains_no_retired_worker():
    source=(Path(__file__).parents[1]/'native/mta_audio_editor_native.spec').read_text()
    assert 'sam_audio_worker.py' not in source and 'sam_audio_compat.py' not in source
