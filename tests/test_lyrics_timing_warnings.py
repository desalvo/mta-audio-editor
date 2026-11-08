"""Word diagnostics against the real Merish encoder and the editor entry point."""
import json
from pathlib import Path
import subprocess

import pytest

from app.merish_mta16 import _colors_section
from app.models import Project
from test_r210_noncommercial_collection_browser import nc_browser_config as nc_browser_config  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'app/static/lyrics_timing.js'
JS = (ROOT / 'app/static/app.js').read_text()
EDITOR = JS[JS.index('function lyricsTimingIssueText('):JS.index("window.addEventListener('pointerdown',e=>{", JS.index('function timedEditorConfig('))]


def node(script):
    result = subprocess.run(['node', '-e', script], cwd=ROOT, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    return result.stdout


def lines_fixture():
    return [
        {'time_ms': 1000, 'end_ms': 2500, 'text': 'Hello world', 'words': [
            {'text': 'Hello', 'start_ms': 1000, 'end_ms': 1500},
            {'text': 'world', 'start_ms': 1600, 'end_ms': 2400},
        ]},
        {'time_ms': 3007, 'end_ms': 5000, 'text': 'Again', 'words': [
            {'text': 'Again', 'start_ms': 3010, 'end_ms': 4900},
        ]},
    ]


@pytest.mark.parametrize('problem,expected', [
    ('valid', None), ('overlap', 'word_overlap'), ('reversed', 'word_duration'),
    ('sub_tick', 'word_duration'), ('before_line', 'word_before_line'),
    ('next_line', 'word_after_next_line'), ('after_audio', 'word_after_audio'),
    ('duplicate', 'line_duplicate'), ('syllable', 'syllable_timing'),
    ('disabled', None), ('deleted', None),
])
def test_word_diagnostics_cover_merish_timing_rejections(problem, expected):
    lines = lines_fixture()
    mode = 'word'
    if problem == 'overlap': lines[0]['words'][1]['start_ms'] = 1400
    elif problem == 'reversed': lines[0]['words'][0]['end_ms'] = 900
    elif problem == 'sub_tick': lines[0]['words'][0].update(start_ms=1001, end_ms=1009)
    elif problem == 'before_line': lines[0]['words'][0]['start_ms'] = 990
    elif problem == 'next_line': lines[0]['words'][1]['end_ms'] = 3002
    elif problem == 'after_audio': lines[1]['words'][0]['end_ms'] = 10001
    elif problem == 'duplicate': lines[1]['time_ms'] = 1000
    elif problem == 'syllable':
        mode = 'character'
        lines[0]['words'][0]['syllables'] = [
            {'text': 'He', 'start_ms': 1000, 'end_ms': 1300},
            {'text': 'llo', 'start_ms': 1200, 'end_ms': 1500},
        ]
    elif problem in ('disabled', 'deleted'):
        lines[0][problem] = True
        lines[0]['words'][0]['end_ms'] = 900
    script = f"require({json.dumps(str(MODULE))});console.log(JSON.stringify(MtaLyricsTiming.issues({json.dumps(lines)},10000,{json.dumps(mode)})));"
    result = json.loads(node(script))
    project = Project(id='timing-fixture', title='Timing', lyrics=lines, merish_lyric_highlight=mode)
    if expected:
        assert expected in {issue['code'] for issue in result}
        with pytest.raises(ValueError): _colors_section(project, 10000, bytes(range(256)))
    else:
        assert result == []
        assert _colors_section(project, 10000, bytes(range(256)))


def test_row_indexes_follow_visible_order_and_inactive_rows_do_not_bound_words():
    lines = lines_fixture()
    lines.insert(1, {'time_ms': 1200, 'text': 'Ignored', 'disabled': True, 'words': []})
    lines[0]['words'][1]['end_ms'] = 3002
    lines.reverse()
    result = json.loads(node(f"require({json.dumps(str(MODULE))});console.log(JSON.stringify(MtaLyricsTiming.issues({json.dumps(lines)},10000)));"))
    issue = next(x for x in result if x['code'] == 'word_after_next_line')
    assert issue['lineIndex'] == 2 and issue['wordIndex'] == 1
    assert issue['otherLineIndex'] == 0 and issue['limit'] == 3000


def test_explicit_line_end_and_close_starts_are_also_reported():
    lines = lines_fixture()
    lines[0]['end_ms'] = 2000
    lines[1]['time_ms'] = 1005
    result = json.loads(node(f"require({json.dumps(str(MODULE))});console.log(JSON.stringify(MtaLyricsTiming.issues({json.dumps(lines)},10000)));"))
    assert {'word_after_line', 'line_precision'} <= {x['code'] for x in result}


def test_preview_is_read_only_and_matches_saved_translation_and_invalidation():
    original = lines_fixture()[0]
    original['words'][0]['syllables'] = [{'text': 'Hello', 'start_ms': 1000, 'end_ms': 1500}]
    node(f"require({json.dumps(str(MODULE))});const assert=require('assert/strict');const original={json.dumps(original)};" + r'''
const before=JSON.stringify(original);
const moved=MtaLyricsTiming.previewLine(original,1500,3000,'Hello world');
assert.equal(moved.words[0].start_ms,1500);
assert.equal(moved.words[0].syllables[0].end_ms,2000);
assert.equal(JSON.stringify(original),before);
assert.equal(MtaLyricsTiming.previewLine(original,1000,2500,'Different').words.length,0);
assert.equal(MtaLyricsTiming.previewLine(original,1000,2000,'Hello world').words.length,0);
assert.equal(MtaLyricsTiming.previewLine(null,1000,null,'New').words.length,0);
''')


@pytest.mark.parametrize('language', ['it', 'en'])
def test_normal_editor_renders_specific_live_warnings_and_escapes_text(language):
    lines = lines_fixture()
    lines[0]['words'][1].update(text='<img src=x onerror=alert(1)>', start_ms=1400)
    setup = f"require({json.dumps(str(MODULE))});const assert=require('assert/strict');let current={{lyrics:{json.dumps(lines)},merish_lyric_highlight:'word'}};let playCursorMs=0;const lang={json.dumps(language)};"
    node(setup + r'''
function tr(en,it){return lang==='it'?it:en}
function esc(s){return String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;')}
function projectDurationMs(){return 10000}
const summary={hidden:true,textContent:''};
let modal='';const rows=current.lyrics.map((line,i)=>({dataset:{originalIndex:String(i)},fields:{
 '.timed-start':{value:line.time_ms/1000},'.timed-end':{value:line.end_ms/1000},'.timed-value':{value:line.text},'.timed-timing-warning':{innerHTML:''}
},classList:{toggle(k,v){this[k]=v}},querySelector(k){return this.fields[k]}}));
const document={getElementById:()=>summary,querySelector:()=>({dataset:{kind:'lyrics'},classList:{add(){}}}),querySelectorAll:()=>rows};
function showUtilityModal(title,html){modal=html}
function requestAnimationFrame(){}
''' + EDITOR + r'''
editTimed('lyrics');
assert(modal.includes('class="timed-timing-warning"'));
assert(modal.includes('oninput="refreshTimedLyricsTimingWarnings()"'));
assert.equal(summary.hidden,false);
assert.equal(rows[0].classList['lyrics-timing-problem'],true);
assert.equal(rows[1].classList['lyrics-timing-problem'],false);
const warning=rows[0].fields['.timed-timing-warning'].innerHTML;
assert(warning.includes('⚠'));assert(warning.includes(lang==='it'?'Parola 2':'Word 2'));
assert(warning.includes('0:01.400'));assert(warning.includes('0:01.500'));
assert(!warning.includes('<img'));assert(warning.includes('&lt;img'));
rows[1].fields['.timed-start'].value='2.000';
rows[1].fields['.timed-end'].value='4.000';
refreshTimedLyricsTimingWarnings();
assert(rows[0].fields['.timed-timing-warning'].innerHTML.includes(lang==='it'?'riga 2':'line 2'));
rows[0].fields['.timed-value'].value='Changed';
refreshTimedLyricsTimingWarnings();assert.equal(summary.hidden,true);
''')


def test_combined_editor_places_warning_on_the_affected_line():
    lines = lines_fixture()
    lines[0]['words'][1]['start_ms'] = 1400
    start = JS.rindex('function lyricsChordsEditorHtml(){')
    combined = JS[start:JS.index('\nfunction refreshLyricsChordsEditor()', start)]
    setup = f"require({json.dumps(str(MODULE))});const assert=require('assert/strict');let current={{lyrics:{json.dumps(lines)},merish_lyric_highlight:'word'}};"
    node(setup + r'''
function tr(en,it){return it}function esc(s){return String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;')}
function projectDurationMs(){return 10000}function editorDraftLyrics(){return current.lyrics}
function editorLineWords(line){return line.words}function editorWordUnits(word){return [{text:word.text,syllable:null}]}
function lyricsChordsEditorPosition(ms){return timedEditorTime(ms)}
let lyricsChordsEditorDraft=[],lyricsChordsEditorMarkersDraft=[],lyricsChordsEditorSelected=-1;
let lyricsChordsEditorUndoStack=[],lyricsChordsEditorRedoStack=[];
''' + EDITOR + combined + r'''
const html=lyricsChordsEditorHtml();
assert.equal((html.match(/class="lyrics-timing-warning"/g)||[]).length,1);
assert(html.includes('Parola 2'));assert(html.includes('0:01.500'));
assert(html.indexOf('Problemi di sincronizzazione')<html.indexOf('Again'));
''')


def test_editor_warning_disclosure_in_chromium(nc_browser_config):
    playwright = pytest.importorskip('playwright.sync_api')
    lines = lines_fixture()
    lines[0]['words'][1]['start_ms'] = 1400
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch(**nc_browser_config)
        page = browser.new_page(viewport={'width': 1000, 'height': 800})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.set_content('<style>' + (ROOT / 'app/static/app.css').read_text() + '</style><div class="utility-modal"><div class="utility-body" id="modal"></div></div>')
        page.add_script_tag(content=MODULE.read_text())
        page.add_script_tag(content='let current=' + json.dumps({'lyrics': lines, 'merish_lyric_highlight': 'word'}) + ';let playCursorMs=0;')
        page.add_script_tag(content=r'''
function tr(en,it){return it}function esc(s){return String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;')}
function projectDurationMs(){return 10000}function showUtilityModal(title,html){document.getElementById('modal').innerHTML=html}
function toast(){}function render(){}function markDirty(){}function closeUtilityModal(){}
'''+EDITOR)
        snapshot_start = JS.index('function ensureEventSnapshot(ev)')
        page.add_script_tag(content=JS[snapshot_start:JS.index('\nfunction newOverrideEvent(', snapshot_start)])
        page.evaluate("editTimed('lyrics')")
        page.locator('.lyrics-timing-warning summary').click()
        assert 'Parola 2' in page.locator('.lyrics-timing-warning').inner_text()
        page.locator('[data-timing-fix]').first.click()
        assert page.locator('.lyrics-timing-warning').count() == 0
        assert page.locator('#lyricsTimingSummary').is_hidden()
        assert page.evaluate('current.lyrics[0].words[1].start_ms') == 1400
        page.evaluate("current.lyrics[0].words[1].end_ms=6000;editTimed('lyrics')")
        page.locator('#lyricsTimingFixAll').click()
        assert page.locator('.lyrics-timing-warning').count() == 0
        page.evaluate("saveTimedEditor('lyrics')")
        assert page.evaluate('current.lyrics[0].words[1].end_ms') == 2500
        assert page.evaluate('MtaLyricsTiming.issues(current.lyrics,10000).length') == 0
        assert not errors
        browser.close()
