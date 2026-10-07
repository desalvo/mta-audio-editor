from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/static/app.js").read_text(encoding="utf-8")


def test_marker_name_blur_reuses_previous_instance_options():
    assert "function markerOptionsTemplateByName(name,timeMs,excludeIndex=null)" in JS
    assert "String(m?.label||'').trim().toLocaleLowerCase()===wanted" in JS
    assert "Number(m.time_ms||0)<target" in JS
    assert "section_indent_enabled:!!src.section_indent_enabled" in JS
    assert "section_indent_mm:Math.max(0,Math.min(100" in JS


def test_new_and_edit_marker_forms_apply_template_on_blur():
    assert 'id="lcMarkerLabel" value="Instrumental" onblur="applyPreviousMarkerOptionsToNewForm()"' in JS
    assert "function applyPreviousMarkerOptionsToNewForm()" in JS
    assert "function applyPreviousMarkerOptionsToEditForm(index)" in JS
    assert "applyPreviousMarkerOptionsToEditForm(${Number(index)})" in JS
    assert "applyMarkerOptionsTemplateToFields" in JS
