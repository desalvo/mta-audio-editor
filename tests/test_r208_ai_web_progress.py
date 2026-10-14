"""Regression checks for the web arranger long-running request feedback."""
from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "app/static/app.js"


def test_arranger_inference_has_visible_indeterminate_progress():
    source = JS.read_text(encoding="utf-8")
    assert 'id="aiRemixJobProgress"' in source
    assert 'id="aiRemixJobElapsed"' in source
    assert 'aria-label="AI generation in progress"' in source
    assert "elapsedTimer=setInterval(updateElapsed,1000)" in source


def test_arranger_prevents_duplicate_inference_requests_and_reenables_button():
    source = JS.read_text(encoding="utf-8")
    assert "if(button?.disabled)return;" in source
    assert "if(button)button.disabled=true;" in source
    assert "if(button?.isConnected)button.disabled=false;" in source
    assert "AI generation failed / Generazione fallita:" in source
