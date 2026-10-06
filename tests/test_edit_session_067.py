from pathlib import Path
R=Path(__file__).resolve().parents[1];J=(R/"app/static/app.js").read_text();N=(R/"native/mta_audio_editor_native.py").read_text()
def test_autosave_manual(): assert "autosaveEnabled=true" in J and "if(!autosaveEnabled)" in J and "Progetto salvato manualmente" in J and "autosave_enabled" in N
def test_undo_redo(): assert "async function undoEdit()" in J and "async function redoEdit()" in J
def test_timeline_editing():
    assert all(f"function {x}(" in J for x in ["cutTimelineSelection","copyTimelineSelection","pasteTimelineSelection","removeTimelineSelection"])
    assert "selectedTrackIdSet=new Set()" in J and "function selectedTrackIds()" in J
def test_shortcuts(): assert all(x in J for x in ["key==='z'","key==='x'","key==='c'","key==='v'","key==='s'"])
