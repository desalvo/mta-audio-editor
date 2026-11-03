"""Optional percussion processing needs a fresh choice in each separation dialog."""
import json
from pathlib import Path
import re
import subprocess

import pytest
from fastapi.testclient import TestClient

from app import ai_arranger_runtime as queue, main, native_ai_routing, storage
from app.models import Clip, Track
from test_r210_media_stems_cleanup import project as project, wav  # noqa: F401


ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / 'app/static/app.js').read_text()
STANDARD = ('vocals', 'drums', 'bass', 'guitar', 'piano', 'other')


def js_function(name):
    start = re.search(r'^(?:async )?function ' + re.escape(name) + r'\(', JS, re.M).start()
    following = re.search(r'\n(?:async )?function \w+\(', JS[start:])
    return JS[start:start + following.start()]


@pytest.mark.parametrize('prefix', ['track', 'stem'])
@pytest.mark.parametrize('choice', ['percussions', 'drums_without_percussions', 'kick', 'snare', 'toms', 'cymbals', 'all_checkbox', 'other', 'lead_vocals'])
def test_real_dialogs_reset_saved_target_and_send_only_current_choices(prefix, choice):
    functions = '\n'.join(js_function(name) for name in (
        'isPercussionStemTarget', 'stemTargetControl', 'syncStemPercussionSelection',
        'stemSeparationSelection', 'restorePercussionMethod', 'openTrackStemWorkflow',
        'syncTrackStemModelCount', 'openStemWorkflow', 'startTrackStemSplit', 'startStemWorkflow',
    ))
    harness = r'''
const assert=require('assert/strict');
const prefix=PREFIX,choice=CHOICE;
let elements={},requests=[],messages=[],activeStemJob=null,activeStemProjectId=null,selectedTrackId=null;
let current={id:'p',title:'Song',target:'DAW',tracks:[{id:'t',name:'Source'}]};
const currentUser={native_single_user:false};
let preferredStemCount=6,preferredStemExecution='server',lastSelectedAudioFile=null;
const pluginInfo={stem_splitter:{available:true,models:['htdemucs_6s'],recommended_model:'htdemucs_6s',
  supported_stem_counts:[6],model_profiles:[{model:'htdemucs_6s',stem_count:6,stem_labels:['vocals','drums','bass','guitar','piano','other']}]} };
const saved={'mta.stem.target':'percussions','mta.percussion.method':'sam-audio-large'},reads=[];
const MtaPreferences={getItem(key){reads.push(key);return saved[key]}};
const $=s=>elements[s.slice(1)],document={getElementById:id=>elements[id]};
function tr(en){return en}function esc(s){return String(s)}function trackById(id){return current.tracks.find(t=>t.id===id)}
function toast(s){messages.push(s)}function supportsLocalIosStems(){return false}function mobilePlatform(){return 'web'}
function setPreferredStemCount(n){preferredStemCount=n}function setMobileBusy(){}function render(){}
async function refresh(){}async function flushAutosave(){}function closeUtilityModal(){}
function showStemProgress(){}function pollStemJob(){}function restoreSingerUi(){}
function collectSingerSelection(){return null}function updateStemWorkflowMode(){}function textModelCatalog(){return {}}
const window={};class FormData{append(){}}
async function api(url){requests.push(url);return {id:'job',project_id:'p',job:{id:'job',project_id:'p'},project:current}}
function showUtilityModal(title,html){
  elements={};
  for(const match of html.matchAll(/<([a-z]+)\b([^>]*\bid="([^"]+)"[^>]*)>/g)){
    const [,tag,attrs,id]=match,classes=new Set((attrs.match(/class="([^"]*)"/)?.[1]||'').split(/\s+/));
    const flags=attrs.replace(/"[^"]*"/g,'""');
    const el={value:attrs.match(/\bvalue="([^"]*)"/)?.[1]||'',checked:/\bchecked\b/.test(flags),
      disabled:/\bdisabled\b/.test(flags),files:[],onchange:attrs.match(/\bonchange="([^"]*)"/)?.[1]||'',
      classList:{toggle(name,on){if(on)classes.add(name);else classes.delete(name)},contains(name){return classes.has(name)}},
      dispatchChange(){eval(this.onchange)}};
    if(tag==='select'){
      const end=html.indexOf('</select>',match.index),body=html.slice(match.index+match[0].length,end);
      el.options=[...body.matchAll(/<option\b([^>]*)>/g)].map(m=>({value:m[1].match(/value="([^"]*)"/)?.[1]||'',selected:/\bselected\b/.test(m[1])}));
      el.value=(el.options.find(o=>o.selected)||el.options[0])?.value||'';
    }
    elements[id]=el;
  }
}
'''
    checks = r'''
const open=()=>prefix==='track'?openTrackStemWorkflow('t'):openStemWorkflow();
const target=()=>stemTargetControl(prefix),checkbox=()=>$(`#${prefix}SplitPercussions`),method=()=>$(`#${prefix}PercussionMethod`);
const run=async()=>{
  const before=requests.length;
  if(prefix==='track')await startTrackStemSplit('t');
  else{elements.stemWorkflowFile.files=[{name:'song.mp3'}];await startStemWorkflow()}
  assert.equal(requests.length,before+1,messages.join('\n'));
  return new URL(requests.at(-1),'https://example.test').searchParams;
};
function standard(){assert.equal(target().value,'all');assert.equal(checkbox().checked,false);
  assert.equal(method().disabled,true);assert.equal(method().value,'dsp');
  assert.equal($(`#${prefix}PercussionMethodRow`).classList.contains('hidden'),true)}
(async()=>{
  open();standard();
  let params=await run();
  assert.equal(params.get('model'),'htdemucs_6s');assert.equal(params.get('stem_count'),'6');
  assert.equal(params.get('stem_targets'),'all');assert.equal(params.get('split_percussions'),'false');
  assert.equal(params.get('percussion_method'),'dsp');
  assert.equal(params.get('split_backing_vocals'),'false');assert.ok(!params.get('singers_json'));
  if(choice==='all_checkbox'){checkbox().checked=true;checkbox().dispatchChange()}
  else{target().value=choice;target().dispatchChange()}
  const percussion=choice!=='other'&&choice!=='lead_vocals';
  assert.equal(checkbox().checked,percussion);assert.equal(method().disabled,!percussion);
  assert.equal($(`#${prefix}PercussionMethodRow`).classList.contains('hidden'),!percussion);
  params=await run();
  assert.equal(params.get('stem_targets'),choice==='all_checkbox'?'all':choice);
  assert.equal(params.get('split_percussions'),String(percussion));
  assert.equal(params.get('percussion_method'),'dsp');
  if(percussion){
    checkbox().checked=false;checkbox().dispatchChange();
    params=await run();assert.equal(params.get('stem_targets'),'all');
    assert.equal(params.get('split_percussions'),'false');assert.equal(params.get('percussion_method'),'dsp');
    // Switching back to all standard stems also turns off an explicit target.
    target().value='percussions';target().dispatchChange();target().value='all';target().dispatchChange();standard();
    // Submission is fail-safe even if an old DOM state bypasses a change event.
    target().value='percussions';params=await run();assert.equal(params.get('stem_targets'),'all');
  }
  open();standard();assert.equal(reads.includes('mta.stem.target'),false);
})().catch(error=>{console.error(error);process.exitCode=1});
'''
    result = subprocess.run(['node'], input=harness.replace('PREFIX', json.dumps(prefix)).replace('CHOICE', json.dumps(choice)) + functions + checks,
                            text=True, capture_output=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('remote', [False, True])
@pytest.mark.parametrize('method', ['dsp', 'mvsep-mega53', 'drumsep-onnx'])
@pytest.mark.parametrize('route', ['track', 'import'])
def test_standard_demucs_publishes_all_stems_without_optional_processors(project, monkeypatch, tmp_path, remote, method, route):
    source = wav(storage.audio_path(project.id, 'source.wav'))
    project.tracks = [Track(id='t', name='Source', filename=source.name, duration_ms=100,
                            clips=[Clip(id='x', source_end_ms=100)])]
    storage.save_project(project)
    monkeypatch.setattr(main, 'NATIVE_SINGLE_USER', True)
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER', 'true')
    monkeypatch.setattr(native_ai_routing, 'is_remote', lambda kind: remote)
    monkeypatch.setattr(main.STEM_SPLITTER, 'available', lambda: not remote)
    monkeypatch.setattr(main.STEM_SPLITTER, 'status', lambda: {
        'available': not remote, 'models': ['htdemucs_6s'], 'supported_stem_counts': [6],
        'model_profiles': [{'model': 'htdemucs_6s', 'stem_count': 6}],
    })
    calls = []

    def forbidden(*args, **kwargs):
        raise AssertionError('Standard Demucs must not invoke optional separation')

    for name in ('_split_drums_percussions', '_drumsep_extract',
                 '_split_lead_backing_vocals'):
        monkeypatch.setattr(main, name, forbidden)
    from app import mega53_runtime
    monkeypatch.setattr(mega53_runtime, 'infer_drums', forbidden)
    monkeypatch.setattr(mega53_runtime, 'infer_drums_vs_percussion', forbidden)

    def split(source, output, **kwargs):
        assert not remote
        assert kwargs['model'] == 'htdemucs_6s' and kwargs['stem_count'] == 6
        calls.append('demucs')
        return [wav(output / f'{name}.wav') for name in STANDARD]

    def remote_infer(kind, source, params):
        assert remote and kind == 'demucs'
        assert params == {'model': 'htdemucs_6s', 'stem_count': 6}
        calls.append('remote-demucs')
        data = wav(tmp_path / 'remote.wav').read_bytes()
        return {'audio': {f'stem_{name}.wav': data for name in STANDARD}}, 'remote-job'

    monkeypatch.setattr(main.STEM_SPLITTER, 'split', split)
    monkeypatch.setattr(main, '_native_remote_infer', remote_infer)
    pending = []
    monkeypatch.setattr(queue, '_spawn', lambda jid, fn, **kw: pending.append(fn))
    client = TestClient(main.app, headers={'x-mta-request': '1'})
    params = {
        'model': 'htdemucs_6s', 'stem_count': 6, 'split_percussions': 'false',
        'stem_targets': 'all', 'percussion_method': method,
    }
    if route == 'track':
        response = client.post(f'/api/projects/{project.id}/tracks/t/stem-jobs', params=params)
    else:
        mp3 = tmp_path / 'song.mp3'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=0.1', str(mp3)], check=True)
        response = client.post('/api/stems/jobs', params={**params, 'project_id': project.id, 'keep_original_track': 'false'},
                               files={'file': ('song.mp3', mp3.read_bytes(), 'audio/mpeg')})
    assert response.status_code == 200, response.text
    jid = (response.json() if route == 'track' else response.json()['job'])['id']
    assert not main.STEM_JOBS[jid]['split_percussions']
    assert set(main.STEM_JOBS[jid]['stem_targets']) == {'all'}
    assert len(pending) == 1
    pending[0](tmp_path / 'progress.json')
    assert main.STEM_JOBS[jid]['status'] == 'completed', main.STEM_JOBS[jid].get('error')
    assert calls == ['remote-demucs' if remote else 'demucs']
    reopened = storage.load_project(project.id)
    assert {track.name for track in reopened.tracks} == {'Source', *(name.title() for name in STANDARD)}
    assert all(storage.audio_path(project.id, track.filename).is_file() for track in reopened.tracks)


@pytest.mark.parametrize('selection', ['all', 'percussions'])
def test_explicit_percussion_request_still_runs_after_demucs(project, monkeypatch, tmp_path, local_native_ai, selection):
    source = wav(storage.audio_path(project.id, 'source.wav'))
    project.tracks = [Track(id='t', name='Source', filename=source.name, duration_ms=100,
                            clips=[Clip(id='x', source_end_ms=100)])]
    storage.save_project(project)
    monkeypatch.setattr(main.STEM_SPLITTER, 'available', lambda: True)
    calls = []

    def split(source, output, **kwargs):
        calls.append('demucs')
        return [wav(output / f'{name}.wav') for name in STANDARD]

    def percussion(source, output):
        assert source.name == 'drums.wav'
        calls.append('percussion')
        return wav(output / 'drums_without_percussions.wav'), wav(output / 'percussions.wav')

    monkeypatch.setattr(main.STEM_SPLITTER, 'split', split)
    monkeypatch.setattr(main, '_split_drums_percussions', percussion)
    pending = []
    monkeypatch.setattr(queue, '_spawn', lambda jid, fn, **kw: pending.append(fn))
    client = TestClient(main.app, headers={'x-mta-request': '1'})
    response = client.post(f'/api/projects/{project.id}/tracks/t/stem-jobs', params={
        'stem_targets': selection, 'split_percussions': str(selection == 'all').lower(),
        'percussion_method': 'dsp',
    })
    assert response.status_code == 200, response.text
    jid = response.json()['id']
    assert main.STEM_JOBS[jid]['split_percussions']
    pending[0](tmp_path / 'progress.json')
    assert main.STEM_JOBS[jid]['status'] == 'completed', main.STEM_JOBS[jid].get('error')
    assert calls == ['demucs', 'percussion']
    names = {track.name for track in storage.load_project(project.id).tracks}
    expected = {'Source', 'Percussions'}
    if selection == 'all':
        expected |= {'Vocals', 'Bass', 'Guitar', 'Piano', 'Other', 'Drums (no percussions)'}
    assert names == expected
