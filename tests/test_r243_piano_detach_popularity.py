from pathlib import Path

from app.models import Project

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/static/app.js").read_text()
CSS = (ROOT / "app/static/app.css").read_text()

def test_piano_keyboard_real_layout():
    assert "whiteMidis.filter(n=>n<midi).length" in JS
    assert "const x=previousWhite*30" in JS
    assert "[1,3,6,8,10].includes(midi%12)" in JS
    assert "width:18px;height:67px" in CSS
    assert "flex:0 0 30px" in CSS
    assert "black-49" not in CSS

def test_popout_chord_lab():
    assert "function pianoOpenDetached()" in JS
    assert "window.open('','mtaPianoChordLab'" in JS
    assert "function pianoPopupClosed()" in JS
    assert "function pianoDetachedKeyClick" in JS
    assert "pianoOpenDetached()" in JS

def test_chord_popularity_is_project_local_and_manual_recency_persistent():
    assert "current?.chord_manual_recency||[]" in JS
    assert "(b.recent||0)-(a.recent||0)" in JS
    assert Project(id="test",title="Test",chord_manual_recency=["g7"]).chord_manual_recency == ["g7"]
