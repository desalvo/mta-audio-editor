from pathlib import Path

JS = (Path(__file__).resolve().parents[1] / "app/static/app.js").read_text()

def test_chord_exclusive_and_additive_selection():
    assert "selectTimelineChordIndex(index,false);" in JS
    assert "if(event.ctrlKey||event.metaKey){selectTimelineChordIndex(index,true);return}" in JS
    assert "else timelineChordSelectedIndices=new Set([index]);" in JS
    assert "timelineChordSelectedIndices.has(index))timelineChordSelectedIndices.delete(index)" in JS

def test_outside_click_clears_without_dom_replacement():
    assert "document.addEventListener('pointerdown',event=>" in JS
    assert "clearTimelineChordSelection();" in JS
    assert "event.target.closest?.('.timeline-chord-marker, #timelineChordContextMenu, #chordShortcutPopover')" in JS
    assert "paintTimelineChordSelection();" in JS
    assert "el.classList.toggle('multi-selected'" in JS
