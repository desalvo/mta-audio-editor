"""Live snapshots settle after editor work without another SSE event."""
from pathlib import Path
import subprocess


SOURCE = (Path(__file__).resolve().parents[1] / 'app/static/project_collaboration.js').read_text()
HARNESS = r'''
const assert=require('assert/strict');const window=globalThis;window.window=window;
const document={getElementById:()=>null,querySelector:()=>null},navigator={};
let source,serial=0;const timers=new Map();
class EventSource{constructor(){source=this;this.handlers={}}addEventListener(kind,fn){this.handlers[kind]=fn}close(){this.closed=true}}
function setTimeout(fn,delay){const id=++serial;timers.set(id,{fn,delay});return id}
function clearTimeout(id){timers.delete(id)}
function tick(){const pending=[...timers.values()];timers.clear();for(const task of pending)task.fn()}
let busy=true,dirty=false,applied=[];
let project={id:'p',title:'Local',owner_user_id:1,shared_with_user_ids:[2],collaboration_revision:1};
const user={id:2},callbacks={isBusy:()=>busy,isDirty:()=>dirty,applyRemote:remote=>applied.push(remote)};
function update(revision){source.handlers.collaboration({data:JSON.stringify({project_id:'p',unread:0,messages:[],latest_message_id:0,
 project:{...project,title:'Remote '+revision,collaboration_revision:revision}})})}
'''


def node(checks):
    result = subprocess.run(['node'], input=HARNESS + SOURCE + checks, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr


def test_busy_snapshot_applies_immediately_after_busy_ends_without_another_event():
    node(r'''
MtaCollaboration.sync(project,user,callbacks);update(2);
assert.equal(applied.length,0);assert.equal(timers.size,1);assert.ok([...timers.values()][0].delay<=100);
busy=false;tick();assert.equal(applied.length,1);assert.equal(applied[0].collaboration_revision,2);assert.equal(timers.size,0);
MtaCollaboration.beforeSave(applied[0]);
''')


def test_new_dirty_edit_stops_polling_and_is_never_replaced_by_pending_remote():
    node(r'''
MtaCollaboration.sync(project,user,callbacks);update(2);dirty=true;busy=false;tick();
assert.equal(applied.length,0);assert.equal(timers.size,0);assert.throws(()=>MtaCollaboration.beforeSave(project),/PROJECT_COLLABORATION_CONFLICT/);
tick();assert.equal(applied.length,0);
dirty=false;MtaCollaboration.saved(project);assert.equal(timers.size,1);tick();assert.equal(applied.length,1);
''')


def test_sync_adopting_current_revision_clears_old_pending_and_prevents_false_guest_conflict():
    node(r'''
MtaCollaboration.sync(project,user,callbacks);update(2);assert.equal(timers.size,1);
project={...project,collaboration_revision:2,title:'Authoritative API result'};dirty=true;
MtaCollaboration.sync(project,user,callbacks);assert.equal(timers.size,0);MtaCollaboration.beforeSave(project);
tick();assert.equal(applied.length,0);
''')


def test_saved_newer_revision_clears_pending_while_busy_without_old_snapshot_replay():
    node(r'''
MtaCollaboration.sync(project,user,callbacks);update(2);
project={...project,collaboration_revision:3};MtaCollaboration.saved(project);
assert.equal(timers.size,0);busy=false;tick();assert.equal(applied.length,0);MtaCollaboration.beforeSave(project);
''')


def test_disconnect_cancels_pending_settlement_timer():
    node(r'''
MtaCollaboration.sync(project,user,callbacks);update(2);const original=source;assert.equal(timers.size,1);
MtaCollaboration.sync(null,user,callbacks);assert.equal(timers.size,0);assert.equal(original.closed,true);
busy=false;tick();assert.equal(applied.length,0);
''')


def test_multiple_busy_updates_share_one_timer_and_apply_only_latest_snapshot():
    node(r'''
MtaCollaboration.sync(project,user,callbacks);update(2);update(3);update(4);assert.equal(timers.size,1);
tick();assert.equal(timers.size,1);assert.equal(applied.length,0);
busy=false;tick();assert.equal(applied.length,1);assert.equal(applied[0].collaboration_revision,4);assert.equal(timers.size,0);
''')


def test_refused_clean_callback_is_retained_without_timer_spin_and_retried_on_sync():
    node(r'''
busy=false;let allow=false,calls=0;
callbacks.applyRemote=remote=>{calls++;if(!allow)return false;applied.push(remote);return true};
MtaCollaboration.sync(project,user,callbacks);update(2);
assert.equal(calls,1);assert.equal(timers.size,0);assert.equal(applied.length,0);
assert.throws(()=>MtaCollaboration.beforeSave(project),/PROJECT_COLLABORATION_CONFLICT/);
allow=true;MtaCollaboration.sync(project,user,callbacks);assert.equal(timers.size,1);tick();
assert.equal(calls,2);assert.equal(applied.length,1);assert.equal(timers.size,0);
''')
