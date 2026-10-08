from pathlib import Path

def test_timeline_marker_shortcut_and_context_labels():
    s=Path('app/static/app.js').read_text()
    assert "e.key.toLowerCase()==='m'" in s
    assert 'addTimelineMarkerAtPlayhead()' in s
    assert 'Aggiungi chord</span>' in s
    assert 'Aggiungi marker</span>' in s
    assert 'Estrai marker</span>' in s
    assert 'Estrai marker automaticamente</span>' not in s

def test_revision_files_synced():
    p=Path('.')
    assert (p/'REVISION').read_text().strip()=='253'
    assert '20253' in (p/'mobile/android/app/build.gradle.kts').read_text()
