import subprocess

import pytest


def test_pdf_chord_and_lyric_stay_together_at_page_break(tmp_path):
    import pymupdf
    from app.models import Chord, LyricLine
    from app.music_text import build_lyrics_pdf
    lines=[LyricLine(time_ms=i*2000,end_ms=i*2000+1500,text=f'LYRIC{i:03d}') for i in range(80)]
    chords=[Chord(time_ms=i*2000,chord=f'CHORD{i:03d}') for i in range(80)]
    out=tmp_path/'song.pdf'
    build_lyrics_pdf(out,title='Boundary',artist='',lyrics=lines,chords=chords,
                     pdf_style={'lyrics':{'size':17},'chords':{'size':15},'line_spacing':4})
    doc=pymupdf.open(out)
    pages=[p.get_text() for p in doc]
    assert len(pages)>1
    for i in range(80):
        lyric=[n for n,p in enumerate(pages) if f'LYRIC{i:03d}' in p]
        chord=[n for n,p in enumerate(pages) if f'CHORD{i:03d}' in p]
        assert len(lyric)==len(chord)==1
        assert lyric==chord,(i,lyric,chord)


def test_pdf_wrapped_lyrics_and_chord_share_a_page_when_they_fit(tmp_path):
    import pymupdf
    from app.models import Chord, LyricLine
    from app.music_text import build_lyrics_pdf
    lines=[LyricLine(time_ms=i*2000,end_ms=i*2000+1500,
            text=f'BEGIN{i:03d} '+('repeated words ' * 13)+f'END{i:03d}') for i in range(40)]
    chords=[Chord(time_ms=i*2000,chord=f'CHORD{i:03d}') for i in range(40)]
    out=tmp_path/'wrapped.pdf'
    build_lyrics_pdf(out,title='Boundary',artist='',lyrics=lines,chords=chords,
                     pdf_style={'lyrics':{'size':17},'chords':{'size':15},'line_spacing':4})
    pages=[p.get_text() for p in pymupdf.open(out)]
    assert len(pages)>1
    for i in range(40):
        locations=[[n for n,p in enumerate(pages) if token in p] for token in
                   (f'BEGIN{i:03d}',f'END{i:03d}',f'CHORD{i:03d}')]
        assert all(len(x)==1 for x in locations) and locations[0]==locations[1]==locations[2],(i,locations)


@pytest.mark.skipif(not __import__('shutil').which('node'),reason='Node required')
def test_lyrics_shift_preserves_nested_timing_anchors_and_undo():
    js=r'''const fs=require('fs'),vm=require('vm'),assert=require('assert');
const src=fs.readFileSync('app/static/app.js','utf8');
const s=src.indexOf('function lcSnapshot()'),e=src.indexOf('\nfunction lcRememberScroll()',s);const f=src.indexOf('function ensureEventSnapshot('),g=src.indexOf('\nfunction ',f+10);
assert.ok(s>=0);let refresh=0;
const c={lyricsChordsEditorLyricsDraft:[{time_ms:100,end_ms:300,words:[{start_ms:110,end_ms:200,syllables:[{start_ms:120,end_ms:140}]}]}],lyricsChordsEditorDraft:[{manual_anchor:true,anchor_line_time_ms:100,time_ms:130},{manual_anchor:false,time_ms:500}],lyricsChordsEditorMarkersDraft:[{manual_lyric_anchor:true,anchor_lyric_time_ms:100,time_ms:99}],lyricsChordsEditorUndoStack:[],lyricsChordsEditorRedoStack:[],lyricsChordsEditorHistoryState:'',refreshLyricsChordsEditor:()=>{refresh++;c.lcCommitHistory()},toast:()=>{},Number,JSON,Map,Set};
vm.createContext(c);vm.runInContext(src.slice(f,g),c);vm.runInContext(src.slice(s,e),c);c.lyricsChordsEditorHistoryState=c.lcSnapshot();assert.equal(c.shiftLyricsDraft(50),true);
assert.equal(c.lyricsChordsEditorLyricsDraft[0].time_ms,150);assert.equal(c.lyricsChordsEditorLyricsDraft[0].words[0].syllables[0].start_ms,170);
assert.equal(c.lyricsChordsEditorDraft[0].anchor_line_time_ms,150);assert.equal(c.lyricsChordsEditorDraft[0].time_ms,130);assert.equal(c.lyricsChordsEditorDraft[1].time_ms,500);
assert.equal(c.lyricsChordsEditorMarkersDraft[0].anchor_lyric_time_ms,150);assert.equal(c.lyricsChordsEditorMarkersDraft[0].time_ms,99);assert.equal(refresh,1);
const before=JSON.stringify(c.lyricsChordsEditorLyricsDraft);assert.equal(c.shiftLyricsDraft(-1000),false);assert.equal(JSON.stringify(c.lyricsChordsEditorLyricsDraft),before);
assert.equal(c.shiftLyricsDraft(50),true);assert.equal(c.lyricsChordsEditorLyricsDraft[0].time_ms,200);c.undoLyricsChordsEditor();assert.equal(c.lyricsChordsEditorLyricsDraft[0].time_ms,150);c.redoLyricsChordsEditor();assert.equal(c.lyricsChordsEditorLyricsDraft[0].time_ms,200);
'''
    subprocess.run(['node','-e',js],check=True)


@pytest.mark.skipif(not __import__('shutil').which('ffmpeg'),reason='FFmpeg required')
def test_gain_applies_only_selected_samples_and_keeps_original_asset(tmp_path,monkeypatch):
    import numpy as np
    import soundfile as sf
    from fastapi.testclient import TestClient
    from app import main,storage
    from app.models import Clip,Track
    monkeypatch.setattr(storage,'ROOT',tmp_path.resolve())
    monkeypatch.setenv('MTA_ALLOW_INSECURE_NO_AUTH','true')
    project=storage.create_project('Gain')
    original=storage.audio_path(project.id,'tone.wav')
    samples=np.full(44100,.1,dtype='float32');sf.write(original,samples,44100,subtype='PCM_24')
    project.tracks=[Track(id='track',name='Tone',filename='tone.wav',duration_ms=1000,channels=1,
        channel_layout='mono',clips=[Clip(id='clip',source_start_ms=0,source_end_ms=1000,timeline_start_ms=0)])]
    storage.save_project(project);before=project.model_dump(mode='json');client=TestClient(main.app,headers={'X-MTA-Request':'1'})
    base=f'/api/projects/{project.id}/tracks/track/sample-editor'
    result=client.post(base+'/effect-apply',json={'effect':'gain','start_sample':11025,'end_sample':22050,'params':{'gain_db':6}})
    assert result.status_code==200,result.text
    saved=result.json()['project'];track=saved['tracks'][0]
    audio,rate=sf.read(storage.audio_path(project.id,track['filename']))
    assert rate==44100 and len(audio)==44100
    assert audio[2000]==pytest.approx(.1,abs=.002)
    assert audio[15000]==pytest.approx(.1*10**(6/20),abs=.002)
    assert audio[30000]==pytest.approx(.1,abs=.002)
    assert original.is_file() and any(item['filename']=='tone.wav' for item in saved['clip_library'])
    assert track['waveform_peaks']
    invalid=client.post(base+'/effect-apply',json={'effect':'gain','start_sample':0,'end_sample':100,'params':{'gain_db':100}})
    assert invalid.status_code==400
    assert storage.load_project(project.id).tracks[0].filename==track['filename']
    # The browser keeps both library entries when restoring the prior project.
    before['clip_library']=saved['clip_library']
    undo=client.put(f'/api/projects/{project.id}',json=before)
    assert undo.status_code==200,undo.text
    assert undo.json()['tracks'][0]['filename']=='tone.wav'
    redo=client.put(f'/api/projects/{project.id}',json=saved)
    assert redo.status_code==200,redo.text
    assert redo.json()['tracks'][0]['filename']==track['filename']
    assert original.is_file() and storage.audio_path(project.id,track['filename']).is_file()
    attenuated=client.post(base+'/effect-apply',json={'effect':'gain','start_sample':0,'end_sample':11025,'params':{'gain_db':-6}})
    assert attenuated.status_code==200,attenuated.text
    softer,_=sf.read(storage.audio_path(project.id,attenuated.json()['track']['filename']))
    assert softer[2000]==pytest.approx(.1*10**(-6/20),abs=.002)


@pytest.mark.skipif(not __import__('shutil').which('node'),reason='Node required')
def test_sample_commit_updates_waveform_and_undo_redo_state():
    js=r'''const fs=require('fs'),vm=require('vm'),assert=require('assert');
const src=fs.readFileSync('app/static/app.js','utf8');
const a=src.indexOf('function projectSnapshot()'),b=src.indexOf('\nfunction editTrackIds()',a);
const x=src.indexOf('async function seCommit('),y=src.indexOf('\nfunction seEnvelope(',x);
assert.ok(a>=0&&b>a&&x>=0&&y>x);
const before={id:'p',tracks:[{id:'t',filename:'old.wav',waveform_peaks:[.1]}],clip_library:[]};
let rendered=[],opened=0,sync=0,invalidated=[];
const c={current:structuredClone(before),sampleEditor:{trackId:'t'},sampleEditorBusy:false,
 undoStack:[],redoStack:[],historyProjectId:'p',lastHistoryState:structuredClone(before),persistedProjectSnapshot:structuredClone(before),
 projectDirty:false,autosaveTimer:null,autosaveBusy:false,autosaveQueued:false,selectedTrackId:'t',
 setTimeout,clearTimeout,JSON,Set,Number,structuredClone,confirm:()=>true,toast:()=>{},updateEditActionState:()=>{},
 render:()=>rendered.push(c.current.tracks[0].waveform_peaks[0]),timingAudioChanged:ids=>invalidated.push([...ids]),
 api:async()=>({project:{id:'p',tracks:[{id:'t',filename:'new.wav',waveform_peaks:[.2]}],clip_library:[{id:'old',filename:'old.wav'},{id:'new',filename:'new.wav'}]}}),
 openSampleEditor:async()=>opened++,syncNativeProjectFile:async()=>sync++,trackById:()=>true,closeUtilityModal:()=>{},markDirty:()=>{},
 collect:()=>{},$:()=>({textContent:''})};
vm.createContext(c);vm.runInContext(src.slice(a,b),c);vm.runInContext(src.slice(x,y),c);
c.persistCurrentProject=async()=>{c.projectDirty=false;c.lastHistoryState=c.projectSnapshot()};
(async()=>{await c.seCommit('effect-apply',{effect:'gain'});assert.equal(c.current.tracks[0].filename,'new.wav');assert.deepEqual(rendered,[.2]);assert.equal(c.undoStack.length,1);assert.equal(c.undoStack[0].clip_library.length,2);
await c.seHistory('undo');assert.equal(c.current.tracks[0].filename,'old.wav');assert.equal(c.current.clip_library.length,2);
await c.seHistory('redo');assert.equal(c.current.tracks[0].filename,'new.wav');assert.equal(opened,3);assert.equal(sync,3);assert.deepEqual(rendered,[.2,.1,.2]);assert.deepEqual(invalidated,[['t'],['t']]);})().catch(e=>{console.error(e);process.exitCode=1});'''
    subprocess.run(['node','-e',js],check=True)


@pytest.mark.skipif(not __import__('shutil').which('ffmpeg'),reason='FFmpeg required')
def test_track_match_analysis_and_partial_speed_pitch_processing(tmp_path,monkeypatch):
    import numpy as np
    import soundfile as sf
    from fastapi.testclient import TestClient
    from app import main,storage,track_match
    from app.models import Clip,Track,Marker
    monkeypatch.setattr(storage,'ROOT',tmp_path.resolve())
    monkeypatch.setenv('MTA_ALLOW_INSECURE_NO_AUTH','true')
    project=storage.create_project('Track match');project.bpm=120;project.base_bpm=120;project.tempo_known=True
    rate=44100;t=np.arange(rate*8)/rate
    for name,hz in [('source',261.6256),('reference',293.6648)]:
        sf.write(storage.audio_path(project.id,name+'.wav'),(.1*np.sin(2*np.pi*hz*t)).astype('float32'),rate,subtype='PCM_24')
        project.tracks.append(Track(id=name,name=name,filename=name+'.wav',duration_ms=8000,channels=1,
             channel_layout='mono',clips=[Clip(id=name+'clip',source_start_ms=0,source_end_ms=8000,timeline_start_ms=0)]))
    storage.save_project(project)
    # The tonal estimate and audio rendering use real signals and FFmpeg. The
    # source is a sustained tone, so rhythmic BPM estimation is explicitly faked.
    monkeypatch.setattr(track_match,'estimate_bpm_and_signature',lambda path:(100.0,'4/4'))
    client=TestClient(main.app,headers={'X-MTA-Request':'1'})
    base=f'/api/projects/{project.id}/tracks/source/sample-editor'
    info=client.post(base+'/match-analysis',json={'reference_track_id':'reference','start_sample':rate,'end_sample':rate*5})
    assert info.status_code==200,info.text
    assert info.json()['pitch_semitones']==2 and info.json()['source_bpm']==100 and info.json()['target_bpm']==120
    assert info.json()['target_bpm_audible']==120
    scaled=storage.load_project(project.id);scaled.base_bpm=100;storage.save_project(scaled)
    scaled_info=client.post(base+'/match-analysis',json={'reference_track_id':'reference','start_sample':rate,'end_sample':rate*5})
    assert scaled_info.status_code==200
    assert scaled_info.json()['target_bpm']==100 and scaled_info.json()['target_bpm_audible']==120
    scaled.base_bpm=120;storage.save_project(scaled)
    def no_pitch(*args):
        raise ValueError('cannot estimate')
    with monkeypatch.context() as patch:
        patch.setattr(track_match,'_pitch_shift',no_pitch)
        unpitched=client.post(base+'/match-analysis',json={'reference_track_id':'reference','start_sample':rate,'end_sample':rate*5})
        assert unpitched.status_code==200 and unpitched.json()['pitch_semitones'] is None
        assert 'manualmente' in unpitched.json()['warning']
    applied=client.post(base+'/effect-apply',json={'effect':'match','start_sample':rate,'end_sample':rate*5,
                         'params':{'tempo_ratio':1.2,'semitones':2}})
    assert applied.status_code==200,applied.text
    audio,sr=sf.read(storage.audio_path(project.id,applied.json()['track']['filename']))
    assert sr==rate and len(audio)/sr==pytest.approx(8-4+4/1.2,abs=.06)
    def frequency(segment):
        window=segment*np.hanning(len(segment));return np.argmax(np.abs(np.fft.rfft(window)))*sr/len(segment)
    assert frequency(audio[rate//4:rate//2])==pytest.approx(261.6,abs=5)
    assert frequency(audio[rate*2:rate*2+rate//2])==pytest.approx(293.7,abs=5)
    project=storage.load_project(project.id);project.metronome_mode='zones'
    project.markers=[Marker(id='change',time_ms=3000,label='change')]
    project.metronome_manual_zone_bpms={'START|change':120,'change|END':90};storage.save_project(project)
    analyzed=client.post(base+'/match-analysis',json={'reference_track_id':'reference','start_sample':rate,'end_sample':rate*5})
    assert analyzed.status_code==200 and analyzed.json()['tempo_changes'] >= 1
    missing=client.post(base+'/match-analysis',json={'reference_track_id':'missing','start_sample':0,'end_sample':rate*5})
    assert missing.status_code==404


@pytest.mark.skipif(not __import__('shutil').which('ffmpeg'),reason='FFmpeg required')
def test_track_match_bpm_estimator_uses_real_rhythmic_audio(tmp_path):
    import numpy as np
    import soundfile as sf
    from app.audio_engine import estimate_bpm_and_signature
    rate=22050;n=rate*12;t=np.arange(n)/rate
    samples=.04*np.sin(2*np.pi*261.6*t)
    for offset in range(0,n,rate//2):
        samples[offset:offset+400]+=.7*np.exp(-np.arange(400)/60)*np.sin(2*np.pi*600*np.arange(400)/rate)
    path=tmp_path/'beat.wav';sf.write(path,samples,rate)
    bpm,_=estimate_bpm_and_signature(path)
    assert bpm==pytest.approx(120,abs=2)


@pytest.mark.skipif(not __import__('shutil').which('node'),reason='Node required')
def test_toolbar_icons_resolve_to_distinct_paths():
    js=r'''const fs=require('fs'),vm=require('vm'),assert=require('assert');
let code=fs.readFileSync('app/static/editor_layout.js','utf8');
code=code.replace("if(document.readyState==='loading')", "window.exposed={pathFor,shapes};if(document.readyState==='loading')");
const c={window:{},document:{readyState:'loading',addEventListener:()=>{}}};vm.createContext(c);vm.runInContext(code,c);
function icon(action){return c.window.exposed.pathFor({id:'',getAttribute:()=>action,matches:()=>false})}
const deletion=['removeTimelineSelection()','deleteSelection(false)','deleteSelection(true)'].map(icon);
assert.equal(new Set(deletion).size,3);assert.ok(deletion.every(Boolean));assert.notEqual(icon('save()'),icon('saveAsProject()'));
'''
    subprocess.run(['node','-e',js],check=True)
