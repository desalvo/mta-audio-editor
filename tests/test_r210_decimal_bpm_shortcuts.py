"""Decimal tempo through editor, metronome PCM, persistence and PDF metadata."""
from pathlib import Path
import subprocess
import wave
import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient
from app import main, storage, audio_engine
from app.models import Clip, Marker, Track
from app.music_text import build_lyrics_pdf

ROOT=Path(__file__).resolve().parents[1]
JS=(ROOT/'app/static/app.js').read_text()


def function(name):
    """Extract an actual top-level JS function, not a reimplemented test copy."""
    start=JS.index('function '+name+'(')
    if JS[max(0,start-6):start]=='async ':start-=6
    first=JS.index('{',start);depth=0;quote=None;escaped=False
    for index in range(first,len(JS)):
        c=JS[index]
        if quote:
            if escaped:escaped=False
            elif c=='\\':escaped=True
            elif c==quote:quote=None
            continue
        if c in ('"',"'",'`'):quote=c;continue
        if c=='{':depth+=1
        elif c=='}':
            depth-=1
            if depth==0:return JS[start:index+1]
    raise AssertionError('Unbalanced JavaScript function '+name)


def node(source):
    subprocess.run(['node','-e',source],check=True,capture_output=True,text=True)


@pytest.fixture
def setup(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'ROOT',tmp_path)
    monkeypatch.setenv('MTA_ALLOW_INSECURE_NO_AUTH','true')
    p=storage.create_project('Decimal tempo')
    p.bpm=p.base_bpm=120.0
    p.tracks=[Track(id='music',name='Music',filename='music.wav',duration_ms=6000,
                    clips=[Clip(id='clip',source_end_ms=6000)])]
    sf.write(storage.audio_path(p.id,'music.wav'),np.zeros(44100*6),44100)
    storage.save_project(p)
    return TestClient(main.app,headers={'X-MTA-Request':'1'}),p


def test_manual_context_value_precision_precedence_and_validation():
    source='\n'.join(function(n) for n in ('parseProjectBpm','formatProjectBpm','setMetronomeManualTempo','projectOriginalBpm','setManualProjectBpm'))
    node('''const assert=require('assert/strict');
let current={bpm:120,base_bpm:120,metronome_bpm:90,metronome_zone_bpms:{0:90},metronome_manual_zone_bpms:{'A|B':87.25}};
const input={},label={};const $=s=>s==='#transportBpmInput'?input:label;
let dirty=0,regens=0;function markDirty(){dirty++}function stopPlayback(){}function scheduleMetronomeTempoRegeneration(){regens++}function toast(){}function tr(en,it){return it}
'''+source+'''
setManualProjectBpm('123,45');assert.equal(current.bpm,123.45);assert.equal(current.base_bpm,123.45);assert.equal(current.original_bpm,120);
assert.equal(current.metronome_bpm,123.45);assert.deepEqual(current.metronome_zone_bpms,{});assert.equal(current.metronome_manual_zone_bpms['A|B'],87.25);
assert.equal(input.value,'123.45');assert.equal(label.textContent,'123.45');assert.equal(regens,1);
for(const invalid of ['',null,'NaN','Infinity','1e2','120junk','12','301'])setManualProjectBpm(invalid);
assert.equal(current.bpm,123.45);assert.equal(regens,1);assert.equal(formatProjectBpm(123.45),'123.45');
''')


def test_muted_metronome_is_regenerated_and_latest_decimal_is_used():
    source=function('scheduleMetronomeTempoRegeneration')
    node('''const assert=require('assert/strict');
let current={id:'p',metronome_mode:'fixed',metronome_bpm:123.45,tracks:[{type:'click',mute:true}]};
let metronomeTempoRegenerationTimer=null,callback,called=0;
function clearTimeout(){}function setTimeout(fn){callback=fn;return 1}
async function createMetronomeTrack(mode){assert.equal(mode,'fixed');assert.equal(current.metronome_bpm,123.45);called++}function toast(){}function tr(en){return en}
'''+source+'''
scheduleMetronomeTempoRegeneration();assert.equal(typeof callback,'function');callback().then(()=>assert.equal(called,1));
''')


@pytest.mark.parametrize('mode',['fixed','zones'])
def test_manual_fractional_grid_beats_automatic_reference_and_survives_reopen(setup,monkeypatch,mode):
    client,p=setup;p.bpm=p.base_bpm=123.45;p.metronome_bpm=123.45;p.metronome_mode=mode
    if mode=='zones':p.markers=[Marker(id='part',time_ms=3000,label='B')]
    storage.save_project(p)
    original=storage.audio_path(p.id,'music.wav').read_bytes()
    def forbidden(*a,**kw):raise AssertionError('Manual BPM must not be replaced by automatic inference')
    monkeypatch.setattr(main,'estimate_adaptive_tempo_map',forbidden)
    monkeypatch.setattr(main,'estimate_bpm_and_signature',forbidden)
    for endpoint,params in (('metronome-track',{'mode':mode,'track_id':'music'}),('metronome-track/refresh',{'time_ms':3500,'track_id':'music'})):
        response=client.post(f'/api/projects/{p.id}/{endpoint}',params=params)
        assert response.status_code==200,response.text
    reloaded=client.get(f'/api/projects/{p.id}').json()
    assert reloaded['bpm']==reloaded['base_bpm']==reloaded['metronome_bpm']==123.45
    assert len([t for t in reloaded['tracks'] if t['type']=='click'])==1
    assert original==storage.audio_path(p.id,'music.wav').read_bytes()
    if mode=='zones':assert all(bpm==123.45 for bpm in reloaded['metronome_zone_bpms'].values())


def test_regeneration_replaces_existing_muted_metronome_pcm(setup):
    client,p=setup
    initial=client.post(f'/api/projects/{p.id}/metronome-track').json()
    before=storage.audio_path(p.id,initial['track']['filename']).read_bytes()
    saved=initial['project'];saved['bpm']=saved['base_bpm']=saved['metronome_bpm']=123.45
    saved['tracks'][-1]['mute']=True
    response=client.put(f'/api/projects/{p.id}',json=saved);assert response.status_code==200,response.text
    response=client.post(f'/api/projects/{p.id}/metronome-track/refresh');assert response.status_code==200,response.text
    result=response.json();assert result['track']['id']==initial['track']['id'] and result['track']['mute']
    assert storage.audio_path(p.id,result['track']['filename']).read_bytes()!=before
    with wave.open(str(storage.audio_path(p.id,result['track']['filename'])),'rb') as wav:
        pcm=np.frombuffer(wav.readframes(wav.getnframes()),dtype='<i2')
        expected=round(60/123.45*wav.getframerate())
    assert np.max(np.abs(pcm[expected:expected+100]))>10000
    assert np.all(pcm[expected-20:expected]==0)


def test_zone_override_is_preserved_under_global_manual_bpm(setup,monkeypatch):
    client,p=setup;p.metronome_mode='zones';p.metronome_bpm=123.45
    p.markers=[Marker(id='part',time_ms=3000,label='B')];p.metronome_manual_zone_bpms={'part|END':87.25};storage.save_project(p)
    result=client.post(f'/api/projects/{p.id}/metronome-track',params={'mode':'zones','track_id':'music'})
    assert result.status_code==200,result.text
    assert result.json()['project']['metronome_zone_bpms']=={'0':123.45,'3000':87.25}


def test_automatic_estimation_keeps_fractional_result_in_api_and_storage(setup,monkeypatch):
    client,p=setup
    monkeypatch.setattr(main,'estimate_bpm_and_signature',lambda *a,**kw:(123.456,'4/4'))
    response=client.post(f'/api/projects/{p.id}/tracks/music/estimate-bpm')
    assert response.status_code==200,response.text
    assert response.json()['bpm']==123.46
    saved=storage.load_project(p.id);assert saved.bpm==saved.base_bpm==123.46


def test_estimator_itself_returns_fractional_bpm(monkeypatch):
    onset=np.zeros(1000);onset[::49]=1
    monkeypatch.setattr(audio_engine,'_rhythm_onset_envelope',lambda *a,**kw:(onset,100.0))
    bpm,_=audio_engine.estimate_bpm_and_signature(Path('unused.wav'))
    assert bpm==122.45 and not bpm.is_integer()


def test_fixed_click_positions_do_not_accumulate_fractional_sample_rounding(setup,tmp_path):
    _,p=setup;p.metronome_bpm=123.45
    target=tmp_path/'click.wav';audio_engine.generate_metronome_wav(p,target)
    with wave.open(str(target),'rb') as wav:
        rate=wav.getframerate();pcm=np.frombuffer(wav.readframes(wav.getnframes()),dtype='<i2')
    # The first sample of each synthesized click is 0; the next is audible.
    for beat in range(1,12):
        start=round(beat*60/123.45*rate)
        assert pcm[start]==0 and pcm[start+1]!=0
        assert np.all(pcm[start-20:start]==0)


def test_pdf_rounds_only_the_displayed_bpm(tmp_path):
    import fitz
    target=tmp_path/'tempo.pdf'
    build_lyrics_pdf(target,title='Decimal BPM',artist='',lyrics=[],chords=[],bpm=123.75)
    with fitz.open(target) as pdf:text=''.join(page.get_text() for page in pdf)
    assert 'BPM: 124' in text and '123.75' not in text


def test_r_shortcut_through_registered_capture_handler_for_click_and_chords():
    helper=function('handleGeneratedTrackShortcut')
    begin=JS.index("window.addEventListener('keydown',e=>{\n  if(handleBounceShortcut(e)||handleGeneratedTrackShortcut(e))")
    end=JS.index('\n},true);',begin)+len('\n},true);')
    node('''const assert=require('assert/strict');class Input{};class Area{};class Select{};
const HTMLInputElement=Input,HTMLTextAreaElement=Area,HTMLSelectElement=Select;
let current={},selectedTrackId='click',timelineTool='select',timelineChordSelectedIndices=new Set(),calls=[],closed=0,handler;
const tracks={click:{id:'click',type:'click'},chords:{id:'chords',type:'keyboards',name:'Chords'},music:{id:'music',type:'audio'}};
function trackById(id){return tracks[id]}function isGeneratedChordsTrack(t){return t.id==='chords'}
function closeTrackContextMenu(){closed++}async function refreshGeneratedTrackFromContext(id){calls.push(id)}
function handleBounceShortcut(){return false}function selectedSegmentItems(){return []}const window={addEventListener(name,fn,capture){assert.equal(capture,true);handler=fn}};
const document={activeElement:null,body:{}};
'''+helper+'\n'+JS[begin:end]+'''
const event=(target,extra={})=>({key:'r',target,repeat:false,ctrlKey:false,metaKey:false,altKey:false,preventDefault(){this.prevented=true},...extra});
let slider=new Input();slider.tagName='INPUT';slider.type='range';let e=event(slider);handler(e);assert.equal(e.prevented,true);
selectedTrackId='chords';handler(event({tagName:'BUTTON'}));assert.deepEqual(calls,['click','chords']);
for(const type of ['text','number','search','password']){let t=new Input();t.tagName='INPUT';t.type=type;handler(event(t))}
for(const extra of [{repeat:true},{ctrlKey:true},{metaKey:true},{altKey:true}]){if(extra.ctrlKey||extra.metaKey)extra.target=new Input();handler(event({},extra))}
handler(event({tagName:'BUTTON',closest:()=>({})}));selectedTrackId='music';handler(event({}));assert.deepEqual(calls,['click','chords']);
''')


def test_tempo_save_waits_for_inflight_autosave_and_never_uses_stale_settings():
    helper=function('persistMetronomeSettings')
    node('''const assert=require('assert/strict');
let current={id:'p',bpm:123.45},autosaveBusy=true,autosaveTimer=1,autosaveQueued=false,projectDirty=true,events=[];
function clearTimeout(){}function setTimeout(fn){events.push('wait');autosaveBusy=false;fn()}
async function persistCurrentProject(){events.push('save');assert.equal(current.bpm,123.45);projectDirty=false}async function syncNativeProjectFile(){events.push('native')}
function markDirty(){}function tr(en){return en}
'''+helper+'''
persistMetronomeSettings().then(()=>{assert.deepEqual(events,['wait','save','native']);assert.equal(autosaveBusy,false)});
''')


def test_context_shortcut_presentation_and_decimal_transport_contract():
    assert '<kbd class="context-shortcut">R</kbd>' in JS and 'aria-keyshortcuts="r"' in JS
    assert 'focusTrackShortcuts(selectedTrackId,event)' in JS
    assert 'focusTrackShortcuts(trackId)' in JS
    assert 'menu.focus({preventScroll:true})' in JS
    html=(ROOT/'app/templates/index.html').read_text()
    assert 'min="30" max="300" step="0.01"' in html
    assert "formatProjectBpm(current.bpm||120)" in JS
    assert '#transportBpmInput{width:84px' in (ROOT/'app/static/app.css').read_text()


def test_generation_uses_persisted_decimal_and_invalidates_audio_cache():
    node("const assert=require('assert/strict');let current={id:'p',bpm:123.45,metronome_bpm:123.45,tracks:[{id:'music',type:'audio'},{id:'click',type:'click',mute:true}]},metronomeCreatePending=false,selectedTrackId=null,events=[];"+
         "async function persistMetronomeSettings(){events.push('save')}async function api(url){assert.ok(url.includes('/metronome-track?'));assert.equal(current.metronome_bpm,123.45);events.push('generate');return {project:current,track:{id:'click'}}}"+
         "async function syncNativeProjectFile(id,strict){assert.equal(id,'p');assert.equal(strict,true);events.push('native-save')}function invalidateTrackAudioCache(id){events.push('invalidate:'+id)}function clearPlaybackWarmCache(){events.push('clear-warm')}function timingAudioChanged(ids){events.push('timing:'+ids[0])}function render(){}async function refresh(){}function toast(){}function trackById(){}"+
         function('formatProjectBpm')+'\n'+function('createMetronomeTrack')+
         "createMetronomeTrack().then(()=>{assert.deepEqual(events,['save','generate','native-save','invalidate:click','clear-warm','timing:click']);assert.equal(metronomeCreatePending,false)})")
