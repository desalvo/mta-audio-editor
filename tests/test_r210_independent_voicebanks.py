from types import SimpleNamespace
import pytest
from app.vocal_synthesis import Settings, validate_voice_lyrics


def test_independent_voicebank_selection():
    cfg=Settings(voice_banks=['air','cicada','quake'])
    parts=[SimpleNamespace(notes=[SimpleNamespace(start_ms=0,duration_ms=500,pitch=60,velocity=96)]) for _ in range(3)]
    validate_voice_lyrics(parts,cfg)
    assert cfg.voice_banks == ['air','cicada','quake']


def test_voicebank_mismatch_rejected_before_load():
    parts=[SimpleNamespace(notes=[SimpleNamespace(start_ms=0,duration_ms=500,pitch=60,velocity=96)]) for _ in range(2)]
    with pytest.raises(ValueError,match='voicebank'):
        validate_voice_lyrics(parts,Settings(voice_banks=['air']))


def test_unrecognized_voicebank_rejected():
    with pytest.raises(ValueError):
        Settings(voice_banks=['unlicensed'])
