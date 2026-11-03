"""Registered participants, real project publication, discussion and expiry."""
import asyncio
from io import BytesIO
import json
from pathlib import Path
import subprocess
import wave
import zipfile

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from PIL import Image
import pytest

from app import auth, storage, project_collaboration as collaboration
from app.models import Clip, Track
from test_r210_legal_documents import cookie


@pytest.fixture
def shared(tmp_path, monkeypatch):
    from app import ai_arranger_runtime
    monkeypatch.setattr(storage, 'ROOT', tmp_path / 'projects')
    monkeypatch.setattr(ai_arranger_runtime, '_ROOT', tmp_path / 'queue')
    monkeypatch.setattr(auth, 'DATA_ROOT', tmp_path / 'auth')
    monkeypatch.setenv('MTA_ADMIN_PASSWORD', 'collaboration-test-admin-password')
    monkeypatch.delenv('MTA_ALLOW_INSECURE_NO_AUTH', raising=False)
    monkeypatch.delenv('MTA_NATIVE_SINGLE_USER', raising=False)
    auth.init_auth_db()
    with auth.db() as con:
        for name in ('owner', 'alice', 'bob', 'outsider'):
            con.execute('INSERT INTO users(username,email,display_name,password_hash,active,email_confirmed,role,created_at,updated_at) VALUES(?,?,?,?,1,1,\'user\',1,1)', (name, name + '@example.test', name.title(), 'unused'))
    users = {name: auth.find_user(name)['id'] for name in ('owner', 'alice', 'bob', 'outsider')}
    project = storage.create_project('Shared <Project>', owner_user_id=users['owner'])
    project.shared_with_user_ids = [users['alice'], users['bob']]
    storage.save_project(project)
    app = FastAPI()
    app.include_router(collaboration.router)

    @app.put('/api/projects/{pid}')
    def put(pid: str, request: Request, body: dict):
        from app.ai_project_lock import project_publication_lock
        with project_publication_lock(pid):
            current, user = collaboration._project(request, pid)
            incoming = type(current).model_validate(body)
            collaboration.validate_edit(current, incoming, user)
            incoming.owner_user_id = current.owner_user_id
            incoming.shared_with_user_ids = current.shared_with_user_ids
            storage.save_project(incoming)
            return incoming

    client = TestClient(app, headers={'X-MTA-Request': '1'})
    monkeypatch.setattr(auth, 'get_smtp_config', lambda: {'host': '', 'from_email': ''})
    return project, users, client


def login(client, users, name):
    client.cookies.update(cookie(users[name]))


def endpoint(project, suffix=''):
    return f'/api/projects/{project.id}/collaboration{suffix}'


def test_messages_are_shared_author_tagged_and_unread_only_for_other_users(shared):
    project, users, client = shared
    login(client, users, 'alice')
    response = client.post(endpoint(project, '/messages'), json={'text': '<script>unsafe()</script>\nHello'})
    assert response.status_code == 200, response.text
    message = response.json()
    assert message['sender'] == 'Alice' and message['user_id'] == users['alice']
    assert message['text'].startswith('<script>')  # Data, escaped only at display.
    assert client.get(endpoint(project)).json()['unread'] == 0
    login(client, users, 'owner')
    status = client.get(endpoint(project)).json()
    assert status['unread'] == 1 and status['messages'][0]['id'] == message['id']
    assert set(user['id'] for user in status['participants']) == {users['owner'], users['alice'], users['bob']}
    assert client.post(endpoint(project, '/read'), json={'message_id': message['id']}).status_code == 200
    assert client.get(endpoint(project)).json()['unread'] == 0
    login(client, users, 'bob')
    assert client.get(endpoint(project)).json()['unread'] == 1


def test_unauthorized_user_cannot_read_post_or_leave(shared):
    project, users, client = shared
    assert client.get(endpoint(project)).status_code == 401
    login(client, users, 'outsider')
    for path, method, body in [('', 'get', None), ('/messages', 'post', {'text': 'x'}), ('/read', 'post', {'message_id': 1}), ('/leave', 'post', None), ('/media/' + 'a' * 32, 'get', None), ('/events', 'get', None)]:
        response = getattr(client, method)(endpoint(project, path), **({'json': body} if body else {}))
        assert response.status_code == 404


@pytest.mark.parametrize('deleted', ['owner', 'alice'])
def test_deleted_account_cannot_bypass_normal_project_access_via_dashboard(shared, monkeypatch, deleted):
    from app import account_lifecycle
    project, users, client = shared;login(client, users, 'alice')
    original = account_lifecycle.is_deleted
    monkeypatch.setattr(account_lifecycle, 'is_deleted', lambda uid: uid == users[deleted] or original(uid))
    assert client.get(endpoint(project)).status_code == 404
    assert client.get(endpoint(project, '/events')).status_code == 404
    assert client.post(endpoint(project, '/messages'), json={'text': 'denied'}).status_code == 404
    assert client.post(endpoint(project, '/leave')).status_code == 404


def test_leave_retains_messages_for_others_and_readd_restores_access(shared):
    project, users, client = shared
    login(client, users, 'alice')
    client.post(endpoint(project, '/messages'), json={'text': 'Keep my annotation'})
    assert client.post(endpoint(project, '/leave')).status_code == 200
    assert client.get(endpoint(project)).status_code == 404
    login(client, users, 'owner')
    assert client.get(endpoint(project)).json()['messages'][0]['text'] == 'Keep my annotation'
    assert client.post(endpoint(project, '/leave')).status_code == 400
    current = storage.load_project(project.id)
    current.shared_with_user_ids.append(users['alice'])
    storage.save_project(current)
    login(client, users, 'alice')
    assert client.get(endpoint(project)).status_code == 200


def test_final_revocation_erases_discussion_and_attachments(shared):
    project, users, client = shared
    login(client, users, 'owner')
    image = BytesIO(); Image.new('RGB', (2, 2), 'blue').save(image, 'PNG')
    message = client.post(endpoint(project, '/media'), files={'file': ('image.png', image.getvalue(), 'image/png')}).json()
    media_path = collaboration._media_path(project.id, message['media_id'])
    assert media_path.is_file()
    current = storage.load_project(project.id);current.shared_with_user_ids = [];storage.save_project(current)
    assert not media_path.exists()
    assert not (storage.pdir(project.id) / 'collaboration.sqlite3').exists()
    assert client.get(endpoint(project)).json()['shared'] is False
    assert client.get(message['media_url']).status_code == 409
    current.shared_with_user_ids = [users['alice']];storage.save_project(current)
    assert client.get(endpoint(project)).json()['messages'] == []


def test_real_wav_upload_expiry_is_permanent_and_read_denies_expired_file(shared):
    project, users, client = shared
    login(client, users, 'alice')
    data = BytesIO()
    with wave.open(data, 'wb') as stream:
        stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(44100);stream.writeframes(b'\0\0' * 4410)
    response = client.post(endpoint(project, '/media'), files={'file': ('voice.wav', data.getvalue(), 'audio/wav')})
    assert response.status_code == 200, response.text
    message = response.json()
    assert message['media_type'] == 'audio/wav'
    assert client.get(message['media_url']).content == data.getvalue()
    path = collaboration._media_path(project.id, message['media_id'])
    assert collaboration.cleanup(project.id, now=message['expires_at'] + 1) == 1
    assert not path.exists() and client.get(message['media_url']).status_code == 404
    status = client.get(endpoint(project)).json()
    assert status['messages'][0]['expired'] and not status['messages'][0]['media_url']


@pytest.mark.parametrize('name,content,mime', [('unsafe.svg', b'<svg><script>alert(1)</script></svg>', 'image/svg+xml'), ('fake.png', b'bad', 'image/png'), ('project.json', b'{}', 'audio/wav')])
def test_unsupported_or_forged_media_is_rejected_without_orphans(shared, name, content, mime):
    project, users, client = shared;login(client, users, 'alice')
    assert client.post(endpoint(project, '/media'), files={'file': (name, content, mime)}).status_code == 400
    assert not list((storage.pdir(project.id) / 'collaboration-media').iterdir())
    assert client.get(endpoint(project)).json()['messages'] == []


def test_media_fetch_rechecks_membership_and_never_accepts_path_components(shared):
    project, users, client = shared;login(client, users, 'alice')
    image = BytesIO();Image.new('RGB', (1, 1)).save(image, 'PNG')
    message = client.post(endpoint(project, '/media'), files={'file': ('x.png', image.getvalue(), 'image/png')}).json()
    current = storage.load_project(project.id);current.shared_with_user_ids.remove(users['alice']);storage.save_project(current)
    assert client.get(message['media_url']).status_code == 404
    login(client, users, 'owner')
    assert client.get(endpoint(project, '/media/not-a-media-id')).status_code == 404
    assert client.get(message['media_url']).headers['cache-control'] == 'private, no-store'


def test_portable_export_never_copies_private_discussion_or_expiring_attachments(shared, tmp_path):
    project, users, client = shared;login(client, users, 'alice')
    image = BytesIO();Image.new('RGB', (1, 1)).save(image, 'PNG')
    client.post(endpoint(project, '/messages'), json={'text': 'Private live annotation'})
    assert client.post(endpoint(project, '/media'), files={'file': ('x.png', image.getvalue(), 'image/png')}).status_code == 200
    path = storage.write_project_archive(project.id, tmp_path / 'project.maeprojz')
    with zipfile.ZipFile(path) as archive:
        assert not any('collaboration.sqlite3' in name or 'collaboration-media' in name for name in archive.namelist())


def test_quota_failure_does_not_publish_message_or_leave_uploaded_file(shared, monkeypatch):
    from app import main
    project, users, client = shared;login(client, users, 'alice')
    def denied(*args):
        from fastapi import HTTPException
        raise HTTPException(413, 'Quota reached')
    monkeypatch.setattr(main, '_ensure_workspace_capacity', denied)
    assert client.post(endpoint(project, '/messages'), json={'text': 'Blocked'}).status_code == 413
    image = BytesIO();Image.new('RGB', (1, 1)).save(image, 'PNG')
    assert client.post(endpoint(project, '/media'), files={'file': ('x.png', image.getvalue(), 'image/png')}).status_code == 413
    assert not list((storage.pdir(project.id) / 'collaboration-media').iterdir())
    assert client.get(endpoint(project)).json()['messages'] == []


def test_email_outbox_includes_project_sender_and_excludes_author(shared, monkeypatch):
    project, users, client = shared;login(client, users, 'alice')
    client.post(endpoint(project, '/messages'), json={'text': 'Please check bar 8'})
    calls = []
    monkeypatch.setattr(auth, 'get_smtp_config', lambda: {'host': 'smtp.example.test', 'from_email': 'mta@example.test'})
    monkeypatch.setattr(auth, 'send_mail', lambda *args, **kwargs: calls.append((args, kwargs)))
    result = collaboration.maintenance_once()
    assert result['emails_sent'] == 2
    assert {args[0][0] for args, kwargs in calls} == {'owner@example.test', 'bob@example.test'}
    for args, kwargs in calls:
        assert project.title in args[1] and 'Alice' in args[1]
        assert project.title in args[2] and 'Alice' in args[2] and 'Please check bar 8' in args[2]
        assert '&lt;Project&gt;' in args[3]
        assert kwargs['message_id'].startswith('<mta-collaboration-')
    assert collaboration.maintenance_once()['emails_sent'] == 0


def test_email_failure_does_not_duplicate_message_and_revoked_recipient_is_cancelled(shared, monkeypatch):
    project, users, client = shared;login(client, users, 'alice')
    response = client.post(endpoint(project, '/messages'), json={'text': 'One message'})
    assert response.status_code == 200
    monkeypatch.setattr(auth, 'get_smtp_config', lambda: {'host': 'smtp.example.test', 'from_email': 'mta@example.test'})
    def fail(*args, **kwargs):
        raise RuntimeError('SMTP unavailable')
    monkeypatch.setattr(auth, 'send_mail', fail)
    assert collaboration.deliver_mail(project.id)['failed'] == 2
    current = storage.load_project(project.id);current.shared_with_user_ids.remove(users['bob']);storage.save_project(current)
    calls = [];monkeypatch.setattr(auth, 'send_mail', lambda *args, **kwargs: calls.append(args))
    assert collaboration.deliver_mail(project.id, now=10**11)['sent'] == 1
    assert len(calls) == 1 and calls[0][0] == ['owner@example.test']
    assert len(client.get(endpoint(project)).json()['messages']) == 1


def test_owner_account_deletion_cancels_queued_discussion_emails(shared, monkeypatch):
    from app import account_lifecycle
    project, users, client = shared;login(client, users, 'alice')
    assert client.post(endpoint(project, '/messages'), json={'text': 'Created before deletion'}).status_code == 200
    monkeypatch.setattr(auth, 'get_smtp_config', lambda: {'host': 'smtp.example.test', 'from_email': 'mta@example.test'})
    sent = [];monkeypatch.setattr(auth, 'send_mail', lambda *args, **kwargs: sent.append(args))
    original = account_lifecycle.is_deleted
    monkeypatch.setattr(account_lifecycle, 'is_deleted', lambda uid: uid == users['owner'] or original(uid))
    assert collaboration.deliver_mail(project.id)['sent'] == 0 and not sent
    with collaboration._db(project.id) as con:
        assert {row[0] for row in con.execute('SELECT state FROM mail_outbox')} == {'cancelled'}


def test_stale_collaborator_rejected_and_owner_merges_unrelated_guest_fields(shared):
    project, users, client = shared
    project.tracks = [Track(id='a', name='A', filename='a.wav', clips=[Clip(id='clip', source_end_ms=1000)], duration_ms=1000), Track(id='b', name='B', filename='b.wav')]
    storage.save_project(project);base = project.model_dump(mode='json')
    login(client, users, 'alice')
    guest = json.loads(json.dumps(base));guest['tracks'][1]['name'] = 'Guest B';guest['artist'] = 'Guest artist'
    response = client.put(f'/api/projects/{project.id}', json=guest)
    assert response.status_code == 200
    assert client.put(f'/api/projects/{project.id}', json=base).status_code == 409
    login(client, users, 'owner');owner = json.loads(json.dumps(base))
    owner['tracks'][0]['name'] = 'Owner A';owner['artist'] = 'Owner artist'
    response = client.put(f'/api/projects/{project.id}', json=owner)
    assert response.status_code == 200, response.text
    saved = response.json()
    assert [track['name'] for track in saved['tracks']] == ['Owner A', 'Guest B']
    assert saved['artist'] == 'Owner artist'
    assert saved['collaboration_revision'] > base['collaboration_revision']
    assert saved['owner_user_id'] == users['owner'] and set(saved['shared_with_user_ids']) == {users['alice'], users['bob']}


def test_owner_merge_preserves_parallel_clip_insert_move_and_deletion():
    base = {'tracks': [{'id': 'a', 'clips': [{'id': 'x', 'timeline_start_ms': 0}, {'id': 'y', 'timeline_start_ms': 1000}]}]}
    guest = {'tracks': [{'id': 'a', 'clips': [{'id': 'x', 'timeline_start_ms': 500}, {'id': 'y', 'timeline_start_ms': 1000}, {'id': 'z', 'timeline_start_ms': 2000}]}]}
    owner = {'tracks': [{'id': 'a', 'clips': [{'id': 'x', 'timeline_start_ms': 0}]}]}
    assert collaboration.merge_owner_snapshot(base, guest, owner)['tracks'][0]['clips'] == [{'id': 'x', 'timeline_start_ms': 500}, {'id': 'z', 'timeline_start_ms': 2000}]


def test_owner_snapshot_outside_history_rejected_instead_of_erasing_current_project(shared):
    project, users, client = shared;login(client, users, 'owner')
    body = project.model_dump(mode='json');body['collaboration_revision'] = 999999
    assert client.put(f'/api/projects/{project.id}', json=body).status_code == 409
    assert storage.load_project(project.id).title == project.title


def test_shared_project_revision_changes_for_background_publication_too(shared):
    project, users, client = shared
    before = project.collaboration_revision
    current = storage.load_project(project.id);current.artist = 'Background change';storage.save_project(current)
    assert current.collaboration_revision == before + 1
    login(client, users, 'bob')
    assert client.get(endpoint(project)).json()['revision'] == before + 1


def test_message_pagination_retains_every_annotation(shared):
    project, users, client = shared;login(client, users, 'alice')
    with collaboration._db(project.id) as con:
        con.executemany('INSERT INTO messages(user_id,sender,text,created_at) VALUES(?,?,?,?)', [(users['alice'], 'Alice', str(i), 1) for i in range(205)])
    first = client.get(endpoint(project)).json()
    assert len(first['messages']) == 200 and first['has_more']
    second = client.get(endpoint(project) + '?after=' + str(first['last_returned_id'])).json()
    assert len(second['messages']) == 5 and not second['has_more']
    assert second['messages'][-1]['text'] == '204'


def test_actual_main_put_preserves_guest_edit_when_stale_owner_saves_and_blocks_stale_guest(shared, monkeypatch):
    from app import main
    project, users, client = shared
    monkeypatch.setattr(main, 'NATIVE_SINGLE_USER', False)
    monkeypatch.setattr(main, 'check_basic_auth', lambda request: False)
    server = TestClient(main.app, headers={'X-MTA-Request': '1'})
    login(server, users, 'owner')
    base = server.get(f'/api/projects/{project.id}').json()
    login(server, users, 'alice')
    guest = json.loads(json.dumps(base));guest['title'] = 'Guest title'
    response = server.put(f'/api/projects/{project.id}', json=guest)
    assert response.status_code == 200, response.text
    assert server.put(f'/api/projects/{project.id}', json=base).status_code == 409
    login(server, users, 'owner')
    owner = json.loads(json.dumps(base));owner['artist'] = 'Owner artist'
    owner['shared_with_user_ids'] = [];owner['owner_user_id'] = users['outsider']
    response = server.put(f'/api/projects/{project.id}', json=owner)
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved['title'] == 'Guest title' and saved['artist'] == 'Owner artist'
    assert saved['owner_user_id'] == users['owner'] and set(saved['shared_with_user_ids']) == {users['alice'], users['bob']}


def test_actual_main_share_window_revoke_removes_access_and_owner_can_readd(shared, monkeypatch):
    from app import main
    project, users, client = shared
    monkeypatch.setattr(main, 'NATIVE_SINGLE_USER', False)
    monkeypatch.setattr(main, 'check_basic_auth', lambda request: False)
    server = TestClient(main.app, headers={'X-MTA-Request': '1'})
    login(server, users, 'alice')
    assert server.get(f'/api/projects/{project.id}/shares').status_code == 404
    assert server.post(endpoint(project, '/messages'), json={'text': 'Keep after revoke'}).status_code == 200
    login(server, users, 'owner')
    assert len(server.get(f'/api/projects/{project.id}/shares').json()) == 2
    assert server.delete(f'/api/projects/{project.id}/shares/{users["alice"]}').status_code == 200
    assert server.get(endpoint(project)).json()['messages'][0]['text'] == 'Keep after revoke'
    login(server, users, 'alice')
    assert server.get(endpoint(project)).status_code == 404
    assert server.put(f'/api/projects/{project.id}', json=project.model_dump(mode='json')).status_code == 404
    login(server, users, 'owner')
    assert server.post(f'/api/projects/{project.id}/shares', json={'identifier': 'alice'}).status_code == 200
    login(server, users, 'alice')
    assert server.get(endpoint(project)).status_code == 200


def test_stream_rechecks_revocation_before_each_update(shared, monkeypatch):
    project, users, client = shared
    user = auth.get_user(users['alice'])
    monkeypatch.setattr(auth, 'require_user', lambda request: user)
    class StreamRequest:
        async def is_disconnected(self):return False
    async def exercise():
        response = await collaboration.events(project.id, StreamRequest())
        stream = response.body_iterator
        first = await anext(stream)
        assert 'event: collaboration' in first and project.title in first
        current = storage.load_project(project.id);current.shared_with_user_ids.remove(users['alice']);storage.save_project(current)
        second = await anext(stream)
        assert 'event: revoked' in second and project.title not in second
        await stream.aclose()
    asyncio.run(exercise())


def test_admin_retention_is_persistent_and_validated(shared):
    project, users, client = shared;login(client, users, 'alice')
    assert client.put('/api/admin/collaboration', json={'attachment_ttl_hours': 48}).status_code == 403
    client.cookies.update(cookie(auth.find_user('admin')['id']))
    assert client.get('/api/admin/collaboration').json()['attachment_ttl_hours'] == 24
    assert client.put('/api/admin/collaboration', json={'attachment_ttl_hours': 48}).status_code == 200
    assert collaboration.settings()['attachment_ttl_hours'] == 48
    for hours in (0, -1, 721, True, '24'):
        assert client.put('/api/admin/collaboration', json={'attachment_ttl_hours': hours}).status_code == 400


@pytest.mark.parametrize('body', [{'text': ''}, {'text': 'x' * 20001}, {'text': 'valid', 'user_id': 123}, {'text': 7}])
def test_bad_messages_rejected(shared, body):
    project, users, client = shared;login(client, users, 'alice')
    assert client.post(endpoint(project, '/messages'), json=body).status_code == 400


def test_actual_client_guards_dirty_snapshots_and_escapes_message_html():
    source = (Path(__file__).resolve().parents[1] / 'app/static/project_collaboration.js').read_text()
    harness = r'''
const assert=require('assert/strict');
const window=globalThis;window.window=window;const callbacks={};
const elements={};const document={getElementById:id=>elements[id]||null,querySelector:()=>null};
const navigator={};let eventSource;
class EventSource{constructor(){eventSource=this;this.handlers={}}addEventListener(kind,handler){this.handlers[kind]=handler}close(){this.closed=true}}
const fetch=async()=>({ok:true,status:200,json:async()=>({})});
window.confirm=()=>true;
'''
    checks = r'''
let dirty=true,applied=[];
let project={id:'p',title:'Original',owner_user_id:1,shared_with_user_ids:[2],collaboration_revision:1};
const user={id:2};
MtaCollaboration.sync(project,{id:3,role:'admin'});assert.equal(eventSource,undefined);
MtaCollaboration.sync(project,user,{isDirty:()=>dirty,applyRemote:(p,force)=>applied.push({p,force})});
for(const id of ['mtaCollaborationWindow','mtaCollaborationTitle','mtaCollaborationMembers','mtaCollaborationLeave','mtaCollaborationMessages'])elements[id]={remove(){},scrollHeight:0,scrollTop:0,clientHeight:100};
const actions={};elements.mtaCollaborationConflict={querySelector:selector=>({addEventListener(type,fn){actions[selector]=fn}})};
eventSource.handlers.collaboration({data:JSON.stringify({project_id:'p',revision:2,unread:1,messages:[{id:1,sender:'<img src=x onerror=alert(1)>',text:'<script>x</script>',color:'red;bad()',created_at:1}],project:{...project,title:'New owner title',collaboration_revision:2}})});
assert.ok(elements.mtaCollaborationMessages.innerHTML.includes('&lt;script&gt;x&lt;/script&gt;'));
assert.ok(elements.mtaCollaborationMessages.innerHTML.includes('&lt;img src=x onerror=alert(1)&gt;'));
assert.ok(!elements.mtaCollaborationMessages.innerHTML.includes('bad()'));
assert.equal(applied.length,0);assert.throws(()=>MtaCollaboration.beforeSave(project),/PROJECT_COLLABORATION_CONFLICT/);
actions['[data-conflict="reload"]']();assert.equal(applied.length,1);assert.equal(applied[0].force,true);assert.equal(applied[0].p.title,'New owner title');
MtaCollaboration.beforeSave(project);
MtaCollaboration.sync({...project,collaboration_revision:2},user,{isDirty:()=>true,applyRemote:()=>false});
eventSource.handlers.collaboration({data:JSON.stringify({project_id:'p',revision:3,unread:0,messages:[],project:{...project,title:'Latest',collaboration_revision:3}})});
actions['[data-conflict="reload"]']();assert.throws(()=>MtaCollaboration.beforeSave(project),/PROJECT_COLLABORATION_CONFLICT/);
dirty=false;MtaCollaboration.saved({...project,collaboration_revision:3});MtaCollaboration.beforeSave(project);
MtaCollaboration.sync(null,user);assert.equal(eventSource.closed,true);
const sent={id:'p',owner_user_id:1,shared_with_user_ids:[2],collaboration_revision:1,artist:'Base',tracks:[{id:'a',name:'A',clips:[{id:'x',timeline_start_ms:0}]},{id:'b',name:'B',clips:[]}]};
const current=JSON.parse(JSON.stringify(sent));current.tracks[0].clips[0].timeline_start_ms=500;current.artist='New local';
const saved=JSON.parse(JSON.stringify(sent));saved.collaboration_revision=2;saved.tracks[1].name='Remote B';saved.artist='Server changed';saved.shared_with_user_ids=[2,3];
const merged=MtaCollaboration.mergeSaved(sent,current,saved);
assert.equal(merged.tracks[0].clips[0].timeline_start_ms,500);assert.equal(merged.tracks[1].name,'Remote B');
assert.equal(merged.artist,'New local');assert.equal(merged.collaboration_revision,2);assert.deepEqual(merged.shared_with_user_ids,[2,3]);
assert.equal(sent.tracks[0].clips[0].timeline_start_ms,0);assert.equal(saved.artist,'Server changed');
'''
    result = subprocess.run(['node'], input=harness + source + checks, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
