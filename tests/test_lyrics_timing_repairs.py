"""Explicit timing repair must survive Save and satisfy the real MTA encoder."""
import json

import pytest

from app.merish_mta16 import _colors_section
from app.models import Project
from test_lyrics_timing_warnings import EDITOR, JS, MODULE, lines_fixture, node


def repair(lines, selected=None, mode='word', duration=10000):
    script = f"require({json.dumps(str(MODULE))});const original={json.dumps(lines)};const before=JSON.stringify(original);"
    script += f"const result=MtaLyricsTiming.repair(original,{duration},{json.dumps(mode)},{json.dumps(selected)});"
    script += "if(JSON.stringify(original)!==before)throw Error('Mutated source');console.log(JSON.stringify(result));"
    return json.loads(node(script))


@pytest.mark.parametrize('problem', ['overlap', 'reversed', 'sub_tick', 'before_line', 'next_line',
                                     'after_audio', 'duplicate', 'precision', 'line_end', 'syllable',
                                     'invalid_start', 'negative_line_end'])
def test_fix_all_preserves_words_and_produces_encodable_timing(problem):
    lines = lines_fixture()
    mode = 'word'
    if problem == 'overlap': lines[0]['words'][1]['start_ms'] = 1400
    elif problem == 'reversed': lines[0]['words'][0]['end_ms'] = 900
    elif problem == 'sub_tick': lines[0]['words'][0].update(start_ms=1001, end_ms=1009)
    elif problem == 'before_line': lines[0]['words'][0]['start_ms'] = 990
    elif problem == 'next_line': lines[0]['words'][1]['end_ms'] = 3500
    elif problem == 'after_audio': lines[1]['words'][0]['end_ms'] = 15000
    elif problem == 'duplicate': lines[1]['time_ms'] = 1000
    elif problem == 'precision': lines[1]['time_ms'] = 1005
    elif problem == 'line_end': lines[0]['end_ms'] = 800
    elif problem == 'invalid_start': lines[0]['time_ms'] = -100
    elif problem == 'negative_line_end': lines[0]['end_ms'] = -100
    elif problem == 'syllable':
        mode = 'character'
        lines[0]['words'][0]['syllables'] = [
            {'text': 'He', 'start_ms': 1000, 'end_ms': 1400},
            {'text': 'llo', 'start_ms': 1200, 'end_ms': 1500},
        ]
    result = repair(lines, mode=mode)
    assert result['ok'], result
    assert result['remaining'] == []
    assert [x['text'] for x in result['lines']] == [x['text'] for x in lines]
    assert [[w['text'] for w in x['words']] for x in result['lines']] == [[w['text'] for w in x['words']] for x in lines]
    project = Project(id='repair-test', title='Repair', lyrics=result['lines'], merish_lyric_highlight=mode)
    assert _colors_section(project, 10000, bytes(range(256)))
    repeated = repair(result['lines'], mode=mode)
    assert repeated['ok'] and not repeated['changedLines']
    assert repeated['lines'] == result['lines']


@pytest.mark.parametrize('selected', [None, {'lineIndex': 0, 'wordIndex': 1, 'code': 'word_overlap'}])
def test_overlap_shortens_previous_word_and_preserves_next_start(selected):
    lines = lines_fixture()
    lines[0]['words'][0]['end_ms'] = 1800
    result = repair(lines, selected)
    assert result['ok']
    assert result['lines'][0]['words'][0]['start_ms'] == 1000
    assert result['lines'][0]['words'][0]['end_ms'] == 1600
    assert result['lines'][0]['words'][1] == lines[0]['words'][1]
    assert result['lines'][1] == lines[1]


def test_late_word_is_shortened_without_changing_its_start():
    lines = lines_fixture()
    lines[0]['words'][1]['end_ms'] = 4000
    result = repair(lines, {'lineIndex': 0, 'wordIndex': 1, 'code': 'word_after_next_line'})
    assert result['ok']
    assert result['lines'][0]['words'][1]['start_ms'] == 1600
    assert result['lines'][0]['words'][1]['end_ms'] == 2500
    assert result['lines'][0]['words'][0] == lines[0]['words'][0]
    assert result['lines'][1] == lines[1]


def test_unrelated_problem_remains_after_individual_fix():
    lines = lines_fixture()
    lines[0]['words'][1]['start_ms'] = 1400
    lines[1]['words'][0]['end_ms'] = 15000
    result = repair(lines, {'lineIndex': 0, 'wordIndex': 1, 'code': 'word_overlap'})
    assert result['ok']
    assert all(issue['lineIndex'] == 1 for issue in result['remaining'])
    assert result['lines'][1] == lines[1]


def test_single_late_word_also_shortens_neighbour_when_only_five_ms_remain():
    lines = lines_fixture()
    lines[0]['end_ms'] = 2000
    lines[0]['words'][0]['end_ms'] = 1995
    lines[0]['words'][1].update(start_ms=2000, end_ms=2100)
    result = repair(lines, {'lineIndex': 0, 'wordIndex': 1, 'code': 'word_after_line'})
    assert result['ok'] and not result['remaining']
    assert result['lines'][0]['words'][0]['end_ms'] == 1990
    assert result['lines'][0]['words'][1]['end_ms'] == 2000
    assert result['lines'][1] == lines[1]


def test_physically_impossible_batch_is_atomic_and_identifies_line():
    lines = lines_fixture()
    lines[0]['words'][1]['start_ms'] = 1400
    lines[1]['end_ms'] = 3011
    result = repair(lines)
    assert not result['ok']
    assert result['reason'] == {'code': 'insufficient_space', 'lineIndex': 1}
    assert result['lines'] == lines and not result['changedLines']


def test_inactive_rows_and_valid_rows_remain_untouched():
    lines = lines_fixture()
    lines[0]['disabled'] = True
    lines[0]['words'][0]['end_ms'] = 0
    result = repair(lines)
    assert result['ok'] and not result['changedLines'] and result['lines'] == lines


def test_fix_all_resolves_a_group_of_colliding_lines():
    lines = lines_fixture()
    lines.append({'time_ms': 1000, 'end_ms': 8000, 'text': 'Last', 'words': [
        {'text': 'Last', 'start_ms': 6000, 'end_ms': 7000},
    ]})
    lines[1]['time_ms'] = 1000
    result = repair(lines)
    assert result['ok'], result
    assert not result['remaining']
    assert _colors_section(Project(id='collision', title='Collision', lyrics=result['lines']), 10000, bytes(range(256)))


def test_bounded_random_word_errors_are_repaired_without_losing_text():
    node(f"require({json.dumps(str(MODULE))});const assert=require('assert/strict');" + r'''
let seed=42;const random=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed%20000};
for(let trial=0;trial<300;trial++){
 const words=Array.from({length:5},(_,i)=>({text:'word'+i,start_ms:random(),end_ms:random()}));
 const original=[{time_ms:1000,end_ms:5000,text:words.map(w=>w.text).join(' '),words}];
 const fixed=MtaLyricsTiming.repair(original,10000);
 assert(fixed.ok,JSON.stringify(fixed));assert.equal(fixed.remaining.length,0);
 assert.deepEqual(fixed.lines[0].words.map(w=>w.text),words.map(w=>w.text));
 assert.equal(MtaLyricsTiming.repair(fixed.lines,10000).changedLines.length,0);
}
''')


def test_timed_editor_fix_stays_in_draft_then_save_keeps_repaired_words():
    lines = lines_fixture()
    lines[0]['words'][0]['end_ms'] = 1800
    setup = f"require({json.dumps(str(MODULE))});const assert=require('assert/strict');let current={{lyrics:{json.dumps(lines)},chords:[],markers:[]}};"
    node(setup + r'''
const initial=JSON.stringify(current);let closed=false;
function tr(en,it){return it}function esc(s){return String(s).replaceAll('<','&lt;').replaceAll('"','&quot;')}
function projectDurationMs(){return 10000}function toast(){}function render(){}function markDirty(){}function closeUtilityModal(){closed=true}
function ensureEventSnapshot(event){event.source_snapshot||=JSON.parse(JSON.stringify(event));event.manual_override=true}
const rows=current.lyrics.map((line,index)=>({dataset:{originalIndex:String(index)},fields:{
 '.timed-start':{value:line.time_ms/1000},'.timed-end':{value:line.end_ms/1000},'.timed-value':{value:line.text},'.timed-timing-warning':{innerHTML:''}
},classList:{toggle(){}},querySelector(k){return this.fields[k]}}));
const document={getElementById:()=>null,querySelector:()=>({dataset:{kind:'lyrics'}}),querySelectorAll:()=>rows};
''' + EDITOR + r'''
assert.equal(fixLyricsTimingIssue('timed',0,1,'word_overlap'),true);
assert.equal(JSON.stringify(current),initial);
assert.equal(rows[0]._lyricsTimingDraft.words[0].end_ms,1600);
saveTimedEditor('lyrics');
assert.equal(current.lyrics[0].words[0].end_ms,1600);
assert.equal(current.lyrics[0].words[1].start_ms,1600);
assert.equal(current.lyrics[1].words[0].end_ms,4900);
assert.equal(current.lyrics[0].manual_override,true);
assert(closed);
''')


def test_combined_fix_is_one_history_step_and_moves_unique_manual_anchors():
    lines = lines_fixture()
    lines[1]['time_ms'] = 12000
    setup = f"require({json.dumps(str(MODULE))});const assert=require('assert/strict');let current={{lyrics:{json.dumps(lines)}}};"
    anchor_start = JS.index('function updateLyricsMarkerAnchors(')
    anchors = JS[anchor_start:JS.index('\nfunction applyLyricsLineTime(', anchor_start)]
    snapshot_start = JS.index('function lcSnapshot(')
    snapshot = JS[snapshot_start:JS.index('\nfunction shiftLyricsDraft(', snapshot_start)]
    history_start = JS.index('function lcApplySnapshot(')
    history = JS[history_start:JS.index('\nfunction lcRememberScroll(', history_start)]
    node(setup + r'''
function tr(en,it){return it}function projectDurationMs(){return 10000}function toast(){}
function ensureEventSnapshot(event){event.source_snapshot||=JSON.parse(JSON.stringify(event));event.manual_override=true}
let lyricsChordsEditorLyricsDraft=JSON.parse(JSON.stringify(current.lyrics));
let lyricsChordsEditorDraft=[{manual_anchor:true,anchor_line_time_ms:12000}];
let lyricsChordsEditorMarkersDraft=[{manual_lyric_anchor:true,anchor_lyric_time_ms:12000}];
let lyricsChordsEditorUndoStack=[],lyricsChordsEditorRedoStack=[],lyricsChordsEditorHistoryState='';
function editorDraftLyrics(){return lyricsChordsEditorLyricsDraft}function refreshLyricsChordsEditor(){lcCommitHistory()}
''' + EDITOR + anchors + snapshot + history + r'''
lcCommitHistory();const initial=lcSnapshot();
assert(applyLyricsTimingRepair('combined'));
assert.equal(lyricsChordsEditorUndoStack.length,1);
assert.equal(lyricsChordsEditorDraft[0].anchor_line_time_ms,9990);
assert.equal(lyricsChordsEditorMarkersDraft[0].anchor_lyric_time_ms,9990);
const fixed=lcSnapshot();undoLyricsChordsEditor();assert.equal(lcSnapshot(),initial);
redoLyricsChordsEditor();assert.equal(lcSnapshot(),fixed);
assert.equal(current.lyrics[1].time_ms,12000);
''')
