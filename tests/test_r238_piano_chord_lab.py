from pathlib import Path

from app.models import Project


ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/static/app.js").read_text()
CSS = (ROOT / "app/static/app.css").read_text()
HTML = (ROOT / "app/templates/index.html").read_text()


def test_project_persists_piano_panel_state_and_width():
    p = Project(id="piano-project", title="Piano")
    assert p.piano_panel_visible is False
    assert p.piano_panel_width_px == 360
    p2 = Project.model_validate({**p.model_dump(), "piano_panel_visible": True, "piano_panel_width_px": 420})
    assert p2.piano_panel_visible is True
    assert p2.piano_panel_width_px == 420


def test_piano_lab_is_toggleable_and_resizable():
    assert 'id="pianoPanelMenuBtn"' in HTML
    assert 'togglePianoPanel()' in HTML
    assert 'function togglePianoPanel()' in JS
    assert 'function bindPianoLabResizer()' in JS
    assert 'data-piano-resize="left"' in JS
    assert 'data-piano-resize="right"' in JS
    assert '.piano-lab-scroll' in CSS and 'overflow:auto' in CSS
    assert 'min-width:250px' in CSS and 'max-width:620px' in CSS


def test_live_piano_and_common_chord_presets_are_present():
    assert 'function pianoPlayMidi' in JS
    assert 'function pianoKeyClick' in JS
    for quality in ['maj', 'min', "'7'", 'maj7', 'm7', 'dim', 'dim7', 'aug', 'sus2', 'sus4']:
        assert quality in JS
    assert 'function pianoPlayPreset' in JS


def test_shift_click_builds_and_recognizes_chord():
    assert "event.shiftKey||pianoShiftCollecting" in JS
    assert "window.addEventListener('keydown',pianoShiftDown)" in JS
    assert "window.addEventListener('keyup',pianoShiftUp)" in JS
    assert 'function pianoRecognizeChord' in JS
    assert "pianoShiftCollecting?(pianoChordNotes.size?'…':'—'):pianoRecognizeChord(pianoChordNotes)" in JS
    assert "pianoChordNotes.add(Number(midi))" in JS
    assert "classList.toggle('active'" in JS
