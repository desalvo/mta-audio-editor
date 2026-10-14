from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / 'app' / 'static' / 'app.js'


def test_stem_orphan_console_wired_to_both_project_inventories():
    source = SOURCE.read_text(encoding='utf-8')
    assert 'refreshNativeStemOrphans()' in source
    assert 'nativeStemOrphanInventory' in source
    assert 'recovered-stem-orphans/quarantine' in source
    assert 'recovered-stem-orphans/${action}' in source


def test_operator_console_keeps_project_bound_and_no_automatic_cleanup():
    source = SOURCE.read_text(encoding='utf-8')
    region = source.split('let nativeStemOrphanActionBusy=false;', 1)[1].split('// Server discovery is read-only', 1)[0]
    assert 'current?.id!==pid' in region
    assert "method:'POST'" in region
    assert 'confirm(' in region
    assert 'document.createElement' in region
    assert 'innerHTML' not in region
    assert 'nativeStemOrphanActionBusy=true' in region
    assert 'finally{nativeStemOrphanActionBusy=false;}' in region
