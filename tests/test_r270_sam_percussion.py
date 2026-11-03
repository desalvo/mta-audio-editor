"""Retired percussion backend is unavailable, not an implicit fallback."""
from pathlib import Path
import pytest
from app import main,ai_unified_adapter

def test_removed_loader_and_prompts_are_not_application_entrypoints():
    assert not hasattr(main,'_sam_audio_extract')
    assert not hasattr(main,'_SAM_PROMPTS')
    assert not Path('app/sam_audio_worker.py').exists()

@pytest.mark.parametrize('model',['sam-audio-small','sam-audio-base','sam-audio-large'])
def test_removed_model_never_reaches_the_unified_runtime(tmp_path,model):
    output=tmp_path/'missing'/'output.wav'
    with pytest.raises(ValueError,match='Unsupported'):
        ai_unified_adapter.infer({'kind':'sam-audio','model':model},output)
    assert not output.parent.exists()
