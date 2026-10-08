from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_icon_only_project_actions():
    page=(ROOT/'app/templates/index.html').read_text()
    for handler in ('newProject()', 'openProjectSelector()', 'save()', 'saveAsProject()', 'showProjectSetup()', 'openExportPanel()'):
        assert f'onclick="{handler}"' in page
    assert 'id="metaPanelMenuBtn"' not in page
    assert 'id="pianoPanelMenuBtn"' not in page
    assert page.count('class="primary-icon-action"') >= 5

def test_collapsible_view_order():
    page=(ROOT/'app/templates/index.html').read_text()
    section=page.split('id="viewToolsPanel"',1)[1].split('</section>',1)[0]
    assert 'sidebar-tools collapsed' in page.split('id="viewToolsPanel"')[0][-64:]
    fragments=["showMetaPanel('lyrics')", "showMetaPanel('chords')", "showMetaPanel('markers')", 'togglePianoPanel()', 'focusTracks()', 'focusInspector()', 'focusMixer()']
    offsets=[section.index(x) for x in fragments]
    assert offsets==sorted(offsets)
    assert 'function toggleViewToolsPanel()' in (ROOT/'app/static/app.js').read_text()
