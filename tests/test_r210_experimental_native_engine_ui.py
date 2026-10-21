"""Static regressions: native and web use shared Studio controls."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_shared_ui_exposes_experimental_engines_and_readiness():
    source=(ROOT/'app/static/studio_extended.js').read_text()
    assert "option('mr-mt3'" in source
    assert "option('yourmt3'" in source
    assert "m?.available?'':'disabled'" in source
    assert 'server or native device' in source

def test_model_management_discloses_runtime_and_rights():
    source=(ROOT/'app/static/ai_studio.js').read_text()
    assert 'Experimental Audio-to-MIDI engines (server and native)' in source
    assert 'An admitted asset does not automatically provision the engine runtime' in source
    assert 'data.models||[]' in source
