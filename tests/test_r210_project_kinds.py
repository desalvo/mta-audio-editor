"""Reversible project content modes: real JSON/media and HTTP publication."""
import json
import wave
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app import storage
from app.models import Track, MidiNote, MidiControl
from app.project_kinds import allows, convert, ProjectKindError


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'ROOT', tmp_path/'projects')
    return tmp_path


def track(project, kind, ident):
    value = Track(id=ident, name=ident, filename=ident+'.wav', kind=kind, duration_ms=50)
    if kind == 'midi':
        value.midi_notes=[MidiNote(id='note', pitch=64, start_ms=3, duration_ms=17)]
        value.midi_controls=[MidiControl(time_ms=1, data=[0xC0, 33])]
    with wave.open(str(storage.audio_path(project.id,value.filename)), 'wb') as output:
        output.setnchannels(1);output.setsampwidth(2);output.setframerate(44100)
        output.writeframes(b'\0'*4410)
    return value


@pytest.mark.parametrize('target,audio,midi', [('DAW',True,False),('DAW_MIDI',True,True),('MIDI',False,True),('MTA8',True,False),('MTA16',True,False)])
def test_explicit_modes_and_persistence(workspace,target,audio,midi):
    project=storage.create_project('Kinds',target)
    assert project.project_kind_version==1
    assert allows(project.target,'audio') is audio
    assert allows(project.target,'midi') is midi
    assert storage.load_project(project.id).target==target


@pytest.mark.parametrize('target,kind', [('DAW','midi'),('MTA8','midi'),('MTA16','midi'),('MIDI','audio')])
def test_new_incompatible_track_never_commits(workspace,target,kind):
    project=storage.create_project('Strict',target)
    before=(storage.pdir(project.id)/'project.json').read_bytes()
    project.tracks.append(track(project,kind,'bad'))
    with pytest.raises(ProjectKindError):storage.save_project(project)
    assert (storage.pdir(project.id)/'project.json').read_bytes()==before


def test_reversible_conversion_preserves_events_media_archive_and_gc(workspace):
    project=storage.create_project('Mixed','DAW_MIDI')
    project.tracks=[track(project,'audio','audio'),track(project,'midi','midi')]
    original={t.id:t.model_dump() for t in project.tracks}
    storage.save_project(project)
    convert(project,'MIDI');storage.save_project(project)
    assert [t.id for t in project.tracks]==['midi']
    assert [t.id for t in project.archived_tracks]==['audio']
    storage.schedule_project_gc(project.id, {'audio.wav','midi.wav'})
    storage.run_project_gc(project.id)
    with pytest.raises(ValueError, match='referenced'):
        storage.delete_project_file(project.id,'audio','audio.wav')
    assert all(storage.audio_path(project.id,name).exists() for name in ('audio.wav','midi.wav'))
    # A stale queued-GC entry cannot omit preserved media from the portable ZIP.
    storage.schedule_project_gc(project.id, {'audio.wav','midi.wav'})
    archive=storage.write_project_archive(project.id,workspace/'converted.maeproj')
    restored=storage.import_project_archive(archive,None)
    assert restored.target=='MIDI' and restored.archived_tracks[0].id=='audio'
    convert(restored,'MTA8');storage.save_project(restored)
    assert [t.id for t in restored.tracks]==['audio']
    assert restored.archived_tracks[0].model_dump()==original['midi']
    convert(restored,'DAW_MIDI');storage.save_project(restored)
    assert not restored.archived_tracks
    assert {t.id:t.model_dump() for t in storage.load_project(restored.id).tracks}==original


def test_legacy_mixed_project_migrates_without_hiding_midi(workspace):
    project=storage.create_project('Legacy','DAW_MIDI')
    project.tracks=[track(project,'audio','audio'),track(project,'midi','midi')]
    raw=project.model_dump();raw['target']='DAW';raw.pop('project_kind_version');raw.pop('archived_tracks')
    (storage.pdir(project.id)/'project.json').write_text(json.dumps(raw))
    actual=storage.load_project(project.id)
    assert actual.target=='DAW_MIDI' and len(actual.tracks)==2
    assert json.loads((storage.pdir(project.id)/'project.json').read_text())['project_kind_version']==1


@pytest.fixture
def client(workspace,monkeypatch):
    from app import main
    from app.midi_routes import register_routes
    app=FastAPI()
    monkeypatch.setattr(main,'_project_for_actor',lambda request,pid:storage.load_project(pid))
    app.add_api_route('/api/projects/{pid}',main.project_put,methods=['PUT'])
    app.add_exception_handler(ProjectKindError,main._project_kind_conflict)
    register_routes(app,lambda request,pid:storage.load_project(pid),lambda fn:fn,lambda *args:None)
    return TestClient(app)


def test_http_conversion_and_authoritative_track_restrictions(client):
    project=storage.create_project('HTTP','DAW')
    route=f'/api/projects/{project.id}'
    denied=client.post(route+'/midi',json={'notes':[]})
    assert denied.status_code==409 and denied.json()['code']=='project_type_conflict'
    body=project.model_dump();body['target']='DAW_MIDI'
    changed=client.put(route,json=body)
    assert changed.status_code==200,changed.text
    created=client.post(route+'/midi',json={'name':'MIDI','notes':[{'pitch':60,'duration_ms':100}]})
    assert created.status_code==200,created.text
    body=created.json();body['target']='MTA8'
    changed=client.put(route,json=body)
    assert changed.status_code==200,changed.text
    body=changed.json();assert not body['tracks'] and len(body['archived_tracks'])==1
    # Client autosave cannot silently remove preserved tracks.
    body['archived_tracks']=[]
    preserved=client.put(route,json=body)
    assert preserved.status_code==200 and len(preserved.json()['archived_tracks'])==1
    body=preserved.json();body['target']='MIDI'
    body['tracks']=[]  # A stale history snapshot cannot discard preserved content.
    restored=client.put(route,json=body)
    assert restored.status_code==200 and restored.json()['tracks'][0]['kind']=='midi'
    assert not restored.json()['archived_tracks']


def test_duplicate_preserved_ids_are_rejected(workspace):
    project=storage.create_project('Duplicates','DAW_MIDI')
    audio=track(project,'audio','audio');project.tracks=[audio];project.archived_tracks=[audio]
    with pytest.raises(ProjectKindError,match='Duplicate'):storage.save_project(project)


def test_project_dialog_exposes_all_modes_and_conversion_disclosure():
    text=(Path(__file__).parents[1]/'app/static/app.js').read_text()
    assert '<option value="DAW_MIDI">Multitrack DAW + MIDI</option>' in text
    assert '<option value="MIDI">MIDI</option>' in text
    assert 'Incompatible tracks are preserved inactive and restored when switching back.' in text


@pytest.mark.parametrize('target,operation', [('DAW','audio-to-midi'),('MTA8','vocal-harmony'),('MIDI','vocal-synthesis')])
def test_incompatible_studio_job_is_rejected_before_queue(workspace,monkeypatch,target,operation):
    from app import studio_jobs
    from app.main import _project_kind_conflict
    project=storage.create_project('Studio type',target)
    app=FastAPI()
    app.add_exception_handler(ProjectKindError,_project_kind_conflict)
    studio_jobs.register_routes(app,lambda request,pid:storage.load_project(pid),lambda request:{'id':0,'role':'admin'},lambda *args:None)
    def forbidden(*args,**kwargs):raise AssertionError('Incompatible job must never be queued')
    monkeypatch.setattr(studio_jobs.queue,'start',forbidden)
    response=TestClient(app).post(f'/api/projects/{project.id}/ai-studio/jobs',json={'operation':operation,'track_ids':['missing'],'end_ms':1000})
    assert response.status_code==409 and response.json()['code']=='project_type_conflict'


def test_failed_conversion_keeps_editor_state_and_success_adopts_server(tmp_path):
    import shutil
    import subprocess
    if not shutil.which('node'):pytest.skip('Node required for editor transaction regression')
    source=(Path(__file__).parents[1]/'app/static/app.js').read_text()
    function=source[source.index('async function saveProjectMetaEditor(){'):source.index('async function downloadProjectLyrics(')]
    script="""const vm=require('vm'),assert=require('assert');
const original={id:'project',title:'Before',target:'DAW_MIDI',time_signature:'4/4',sample_rate:44100,bpm:120,tracks:[{id:'m',kind:'midi'}],archived_tracks:[]};
const values={projectMetaTitle:'After',projectMetaTarget:'MIDI',projectMetaTimeSignature:'4/4',projectMetaBpm:'120'};
let submitted;
const state={current:structuredClone(original),autosaveTimer:null,autosaveBusy:false,autosaveQueued:false,projectDirty:true,toast:()=>{},closeUtilityModal:()=>{},render:()=>{},markDirty:()=>{},collect:()=>{},persistCurrentProject:async()=>{},clearTimeout,setTimeout,$:id=>values[id.slice(1)]===undefined?null:{value:values[id.slice(1)]},api:async(path,request)=>{submitted=JSON.parse(request.body);throw Error('HTTP409');}};
vm.createContext(state);vm.runInContext(FUNCTION_SOURCE,state);
(async()=>{await state.saveProjectMetaEditor();assert.deepStrictEqual(state.current,original);assert.equal(submitted.target,'MIDI');assert.equal(state.autosaveBusy,false);
state.api=async()=>({...submitted,tracks:[{id:'m',kind:'midi'}],archived_tracks:[{id:'a',kind:'audio'}]});await state.saveProjectMetaEditor();assert.equal(state.current.target,'MIDI');assert.equal(state.current.archived_tracks.length,1);assert.equal(state.autosaveBusy,false);})();
""".replace('FUNCTION_SOURCE',json.dumps(function))
    path=tmp_path/'conversion.cjs';path.write_text(script)
    subprocess.run(['node',str(path)],check=True,capture_output=True,text=True,timeout=15)


def test_conversion_limit_keeps_the_original_project_unchanged():
    from app.models import Project, Track
    from app.project_kinds import convert, ProjectKindError
    import pytest
    audio = [Track(id=f'a{i}', name='Audio', filename=f'a{i}.wav', duration_ms=1000) for i in range(1024)]
    midi = Track(id='m', name='MIDI', filename='anchor.wav', duration_ms=1000, kind='midi')
    project = Project(id='limit', title='Limit', target='DAW', project_kind_version=1, tracks=audio, archived_tracks=[midi])
    with pytest.raises(ProjectKindError, match='1024'):
        convert(project, 'DAW_MIDI')
    assert project.target == 'DAW'
    assert len(project.tracks) == 1024
    assert project.archived_tracks[0].id == 'm'
