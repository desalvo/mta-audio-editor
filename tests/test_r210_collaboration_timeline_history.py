"""Actual history/remote-refresh functions through shared timeline publication."""
import json
import subprocess
import wave

import pytest
from fastapi.testclient import TestClient

from app import main, storage
from app.models import Clip, Track
from test_r210_project_collaboration import shared as shared, login  # noqa: F401
from test_r210_project_collaboration_integration import COMMON, CLIENT, actual_function, node


def functions(*names):
    return '\n'.join(actual_function(name) for name in names)


@pytest.mark.parametrize('actor', ['owner', 'alice'])
def test_real_shared_timeline_save_then_undo_redo_uses_current_revision(shared, actor):
    project, users, _ = shared
    source = storage.audio_path(project.id, 'timeline.wav')
    with wave.open(str(source), 'wb') as stream:
        stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(44100)
        stream.writeframes(b'\0\0' * 44100)
    project.tracks = [Track(id='t', name='Track', filename=source.name, duration_ms=1000,
                            clips=[Clip(id='clip', source_start_ms=0, source_end_ms=500, timeline_start_ms=0)])]
    storage.save_project(project)
    original = storage.load_project(project.id).model_dump(mode='json')
    client = TestClient(main.app, headers={'X-MTA-Request': '1'})
    login(client, users, actor)
    moved = json.loads(json.dumps(original));moved['tracks'][0]['clips'][0]['timeline_start_ms'] = 250
    saved = client.put(f'/api/projects/{project.id}', json=moved)
    assert saved.status_code == 200, saved.text
    current = saved.json()
    harness = '''let current=CURRENT,selectedTrackId=null,projectDirty=false,lastHistoryState=null;
function render(){}function timingAudioChanged(){}function projectSnapshot(){return JSON.parse(JSON.stringify(current))}
function updateEditActionState(){}function toast(){}async function persistCurrentProject(){}
'''.replace('CURRENT', json.dumps(current))
    source_js = harness + functions('restoreHistorySnapshot')
    source_js += '\nrestoreHistorySnapshot(' + json.dumps(original) + ',"Undo").then(()=>process.stdout.write(JSON.stringify(current)));'
    result = subprocess.run(['node'], input=source_js, text=True, capture_output=True, check=True)
    undo_payload = json.loads(result.stdout)
    undone = client.put(f'/api/projects/{project.id}', json=undo_payload)
    assert undone.status_code == 200, undone.text
    assert undone.json()['tracks'][0]['clips'][0]['timeline_start_ms'] == 0
    assert undone.json()['collaboration_revision'] > current['collaboration_revision']
    redo_harness = harness.replace(json.dumps(current), json.dumps(undone.json()))
    redo_js = redo_harness + functions('restoreHistorySnapshot')
    redo_js += '\nrestoreHistorySnapshot(' + json.dumps(current) + ',"Redo").then(()=>process.stdout.write(JSON.stringify(current)));'
    result = subprocess.run(['node'], input=redo_js, text=True, capture_output=True, check=True)
    redone = client.put(f'/api/projects/{project.id}', json=json.loads(result.stdout))
    assert redone.status_code == 200, redone.text
    assert redone.json()['tracks'][0]['clips'][0]['timeline_start_ms'] == 250
    assert redone.json()['collaboration_revision'] > undone.json()['collaboration_revision']


def test_clean_remote_refresh_rebases_history_without_erasing_other_track_edit():
    harness = COMMON + "\nconst document={getElementById:()=>null,querySelector:()=>null},navigator={};\n"
    node(harness + CLIENT + functions('rebaseSharedProjectHistory', 'applySharedRemoteProject',
                                     'restoreHistorySnapshot', 'undoEdit', 'checkpointHistory') + r'''
let selectedTrackId='a',historyProjectId='p',timelineTargetTrackId=null,timelineClipboard=null;
let undoStack=[JSON.parse(JSON.stringify(current))],redoStack=[];
current.collaboration_revision=2;current.tracks[0].volume_db=-3;lastHistoryState=projectSnapshot();projectDirty=false;
const remote=JSON.parse(JSON.stringify(current));remote.collaboration_revision=3;remote.tracks[1].volume_db=-6;
assert.equal(applySharedRemoteProject(remote),true);
function ensureSessionHistory(){}function updateEditActionState(){}
async function persistCurrentProject(){assert.equal(current.collaboration_revision,3);current.collaboration_revision=4;projectDirty=false}
(async()=>{await undoEdit();assert.equal(current.tracks[0].volume_db,0);assert.equal(current.tracks[1].volume_db,-6);
 assert.equal(current.collaboration_revision,4);assert(audioChanges.some(ids=>ids.includes('b')));
})().catch(error=>{console.error(error);process.exitCode=1});
''')


def test_remote_changes_to_same_track_take_precedence_in_old_history():
    harness = COMMON + "\nconst document={getElementById:()=>null,querySelector:()=>null},navigator={};\n"
    node(harness + CLIENT + functions('rebaseSharedProjectHistory', 'applySharedRemoteProject') + r'''
let undoStack=[JSON.parse(JSON.stringify(current))],redoStack=[];
current.collaboration_revision=2;current.tracks[0].volume_db=-3;projectDirty=false;
const remote=JSON.parse(JSON.stringify(current));remote.collaboration_revision=3;remote.tracks[0].volume_db=-9;
assert.equal(applySharedRemoteProject(remote),true);
assert.equal(undoStack[0].tracks[0].volume_db,-9);assert.equal(undoStack[0].collaboration_revision,3);
assert.equal(current.tracks[0].volume_db,-9);
''')


def test_remote_snapshot_received_during_direct_history_save_settles_without_new_event():
    harness = COMMON + r'''
const document={getElementById:()=>null,querySelector:()=>null},navigator={};
let source,serial=0;const timers=new Map(),applied=[];
class EventSource{constructor(){source=this;this.handlers={}}addEventListener(kind,fn){this.handlers[kind]=fn}close(){}}
function setTimeout(fn,delay){const id=++serial;timers.set(id,{fn,delay});return id}
function clearTimeout(id){timers.delete(id)}
function tick(){const pending=[...timers.values()];timers.clear();for(const task of pending)task.fn()}
'''
    node(harness + CLIENT + functions('persistCurrentProject') + r'''
(async()=>{
 MtaCollaboration.sync(current,currentUser,{isDirty:()=>projectDirty,isBusy:()=>false,
  applyRemote:remote=>{current=remote;applied.push(remote)}});
 let release;apiHandler=()=>new Promise(resolve=>{release=resolve});const task=persistCurrentProject();
 const saved=JSON.parse(JSON.stringify(current));saved.collaboration_revision=2;
 const remote=JSON.parse(JSON.stringify(saved));remote.collaboration_revision=3;remote.tracks[1].volume_db=-6;
 source.handlers.collaboration({data:JSON.stringify({project_id:'p',unread:0,messages:[],latest_message_id:0,project:remote})});
 release(saved);await task;assert.equal(projectDirty,false);tick();
 assert.equal(applied.length,1);assert.equal(current.collaboration_revision,3);assert.equal(current.tracks[1].volume_db,-6);
})().catch(error=>{console.error(error);process.exitCode=1});
''')


def test_remote_refresh_is_refused_while_pointer_clip_drag_is_active():
    node(COMMON + functions('applySharedRemoteProject') + r'''
timelineClipDrag={pointerId:1};projectDirty=false;
const previous=current,remote=JSON.parse(JSON.stringify(current));remote.collaboration_revision=2;remote.tracks[0].volume_db=-6;
assert.equal(applySharedRemoteProject(remote),false);assert.equal(current,previous);assert.equal(rendered,0);assert.equal(audioChanges.length,0);
''')


def test_remote_manual_tempo_reset_refreshes_audio_when_displayed_bpm_is_unchanged():
    node(COMMON + functions('applySharedRemoteProject') + r'''
projectDirty=false;current.bpm=120;current.base_bpm=100;
const remote=JSON.parse(JSON.stringify(current));remote.base_bpm=120;remote.collaboration_revision=2;
assert.equal(applySharedRemoteProject(remote),true);
assert.deepEqual(audioChanges,[['a','b']]);assert.equal(current.bpm/current.base_bpm,1);
''')
