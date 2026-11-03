"""Execute actual editor integration functions with deterministic browser mocks."""
from pathlib import Path
import re
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'app/static/app.js').read_text()
CLIENT = (ROOT / 'app/static/project_collaboration.js').read_text()


def actual_function(name):
    start = re.search(r'^(?:async )?function ' + re.escape(name) + r'\(', APP, re.M).start()
    following = re.search(r'\n(?:async )?function \w+\(', APP[start:])
    assert following, name
    return APP[start:start + following.start()]


def node(source):
    result = subprocess.run(['node'], input=source, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr


COMMON = r'''
const assert=require('assert/strict');
const window=globalThis;window.window=window;
let current={id:'p',title:'Original',owner_user_id:1,shared_with_user_ids:[2],collaboration_revision:1,
 tracks:[{id:'a',name:'A',volume_db:0,clips:[]},{id:'b',name:'B',volume_db:0,clips:[]}]};
let currentUser={id:2},projectDirty=true,autosaveBusy=false,timelineMediaBusy=false,timelineClipDrag=null;
let autosaveTimer=7,autosaveQueued=true,persistedProjectSnapshot=JSON.parse(JSON.stringify(current)),lastHistoryState=null;
let projectMutationSerial=1,rendered=0,resets=0,apiCalls=0,audioChanges=[],messages=[],cleared=[];
function toast(s){messages.push(s)}function tr(en){return en}
function clearTimeout(timer){cleared.push(timer)}function render(){rendered++}
function resetSessionHistory(){resets++}function timingAudioChanged(ids){audioChanges.push([...ids].sort())}
function projectSnapshot(){return JSON.parse(JSON.stringify(current))}function collect(){}
const label={textContent:''},$=()=>label;
let apiHandler=async()=>JSON.parse(JSON.stringify(current));
async function api(...args){apiCalls++;return apiHandler(...args)}
async function reconcileAiProject(){throw Error('Unexpected AI reconciliation')}
'''


@pytest.mark.parametrize('busy', ['autosave', 'timeline'])
def test_explicit_shared_reload_does_not_override_an_active_media_or_save_operation(busy):
    node(COMMON + actual_function('applySharedRemoteProject') + f"\n{('autosaveBusy' if busy == 'autosave' else 'timelineMediaBusy')}=true;\n" + r'''
const before=JSON.stringify(current),remote={...current,title:'Remote'};
assert.equal(applySharedRemoteProject(remote,true),false);
assert.equal(JSON.stringify(current),before);assert.equal(projectDirty,true);assert.equal(resets,0);assert.equal(rendered,0);
''')


def test_dirty_remote_snapshot_requires_explicit_reload_and_name_edits_keep_audio_playing():
    node(COMMON + actual_function('applySharedRemoteProject') + r'''
const original=current,remote=JSON.parse(JSON.stringify(current));remote.title='Owner project';remote.tracks[0].name='Renamed';
assert.equal(applySharedRemoteProject(remote),false);assert.equal(current,original);assert.equal(projectDirty,true);
assert.equal(applySharedRemoteProject(remote,true),true);assert.equal(current,remote);assert.equal(projectDirty,false);
assert.equal(autosaveTimer,null);assert.deepEqual(cleared,[7]);assert.equal(resets,1);assert.equal(rendered,1);
assert.equal(audioChanges.length,0);assert.equal(persistedProjectSnapshot.title,'Owner project');
''')


def test_clean_remote_audio_edit_invalidates_only_changed_tracks_without_resetting_local_history():
    node(COMMON + actual_function('applySharedRemoteProject') + r'''
projectDirty=false;const remote=JSON.parse(JSON.stringify(current));remote.tracks[0].volume_db=-4;remote.tracks[1].color='#123456';
assert.equal(applySharedRemoteProject(remote),true);assert.deepEqual(audioChanges,[['a']]);assert.equal(resets,0);assert.equal(rendered,1);
''')


@pytest.mark.parametrize('owner', [False, True])
def test_shared_access_end_blocks_guest_autosave_but_owner_can_keep_saving(owner):
    functions = actual_function('sharedAccessEnded') + '\n' + actual_function('persistCurrentProject')
    node(COMMON + functions + ('\ncurrentUser={id:1};\n' if owner else '\ncurrentUser={id:2};\n') + r'''
(async()=>{
 const owner=currentUser.id===current.owner_user_id;current.collaboration_access_revoked=true;
 sharedAccessEnded();assert.deepEqual(current.shared_with_user_ids,[]);
 if(owner){
  assert.equal(current.collaboration_access_revoked,undefined);assert.equal(autosaveTimer,7);assert.equal(autosaveQueued,true);
  await persistCurrentProject();assert.equal(apiCalls,1);assert.equal(projectDirty,false);
 }else{
  assert.equal(current.collaboration_access_revoked,true);assert.equal(autosaveTimer,null);assert.equal(autosaveQueued,false);
  await assert.rejects(()=>persistCurrentProject(),/Condivisione terminata/);assert.equal(apiCalls,0);assert.equal(projectDirty,true);
 }
})().catch(error=>{console.error(error);process.exitCode=1});
''')


def test_inflight_save_merges_new_local_edit_with_remote_guest_result_and_updates_dashboard_copy():
    harness = r'''
const document={getElementById:()=>null,querySelector:()=>null};const navigator={};
'''
    node(COMMON + harness + CLIENT + actual_function('persistCurrentProject') + r'''
(async()=>{
 const realMerge=MtaCollaboration.mergeSaved,savedCopies=[];let release;
 globalThis.MtaCollaboration={beforeSave(){},mergeSaved:realMerge,saved:p=>savedCopies.push(p)};
 apiHandler=()=>new Promise(resolve=>{release=resolve});
 const task=persistCurrentProject();assert.equal(apiCalls,1);
 const returned=JSON.parse(JSON.stringify(current));returned.tracks[1].name='Remote guest B';returned.collaboration_revision=2;
 current.tracks[0].name='New typing A';projectMutationSerial++;
 release(returned);await task;
 assert.deepEqual(current.tracks.map(t=>t.name),['New typing A','Remote guest B']);assert.equal(current.collaboration_revision,2);
 assert.equal(projectDirty,true);assert.equal(autosaveQueued,true);assert.equal(savedCopies.length,2);
 assert.equal(savedCopies[0],returned);assert.equal(savedCopies[1],current);
 assert.equal(savedCopies[1].tracks[0].name,'New typing A');assert.equal(persistedProjectSnapshot.collaboration_revision,1);
})().catch(error=>{console.error(error);process.exitCode=1});
''')


def test_inflight_response_cannot_replace_a_different_open_project():
    node(COMMON + actual_function('persistCurrentProject') + r'''
(async()=>{
 let release,saved=0;globalThis.MtaCollaboration={beforeSave(){},saved(){saved++}};
 apiHandler=()=>new Promise(resolve=>{release=resolve});const original=current;
 const task=persistCurrentProject();current={id:'different',title:'Other project',tracks:[]};release(original);await task;
 assert.equal(current.id,'different');assert.equal(saved,0);assert.equal(projectDirty,true);
})().catch(error=>{console.error(error);process.exitCode=1});
''')


def test_server_conflict_opens_recovery_and_keeps_local_state():
    node(COMMON + actual_function('persistCurrentProject') + r'''
(async()=>{
 const original=JSON.stringify(current);let conflicts=0;globalThis.MtaCollaboration={beforeSave(){},conflict(){conflicts++}};
 apiHandler=async()=>{throw Error('PROJECT_COLLABORATION_CONFLICT')};
 await assert.rejects(()=>persistCurrentProject(),/PROJECT_COLLABORATION_CONFLICT/);
 assert.equal(conflicts,1);assert.equal(JSON.stringify(current),original);assert.equal(projectDirty,true);
})().catch(error=>{console.error(error);process.exitCode=1});
''')


def test_actual_editor_render_mounts_dashboard_outside_sidebar_groups_and_disconnects_on_close():
    render = actual_function('render')
    # Execute the real mount hook, then stop before unrelated waveform painting.
    harness = r'''
const assert=require('assert/strict');const window=globalThis;window.window=window;
const elements={},nav={prepend(button){elements[button.id]=button;this.button=button}};
const document={getElementById:id=>elements[id]||null,querySelector:selector=>selector==='.sidebar nav'?nav:null,
 createElement:tag=>({tag,addEventListener(){},remove(){delete elements[this.id]},setAttribute(){}})};
const navigator={};let source;
class EventSource{constructor(){source=this}addEventListener(){}close(){this.closed=true}}
let current={id:'p',owner_user_id:1,shared_with_user_ids:[2],tracks:[]},currentUser={id:2};
let projectDirty=false,autosaveBusy=false,timelineMediaBusy=false,segmentSelectionProject=null,selectedTimelineSegments=new Set();
const stop=Symbol('stop');function rememberActiveWebProject(){throw stop}
function applySharedRemoteProject(){}function sharedAccessEnded(){}function toast(){}
const MtaTimelineRules={key:(t,c)=>t.id+':'+c.id};
'''
    node(harness + CLIENT + render + r'''
try{render()}catch(error){assert.equal(error,stop)}
assert.equal(nav.button.id,'mtaCollaborationNav');assert.equal(nav.button.tag,'button');
assert.ok(nav.button.innerHTML.includes('Dashboard condivisa'));assert.ok(nav.button.innerHTML.includes('mtaCollaborationBadge'));
assert.ok(source);current=null;
try{render()}catch(error){assert.equal(error,stop)}
assert.equal(elements.mtaCollaborationNav,undefined);assert.equal(source.closed,true);
''')
