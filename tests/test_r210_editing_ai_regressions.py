"""Regression checks for edited timeline audio and installed AI runtimes."""
import io
import json
import subprocess
import sys
import venv
import wave
import zipfile
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf


@pytest.mark.parametrize('kind', ['lyrics', 'chords'])
@pytest.mark.parametrize('changed_during_analysis', [False, True])
def test_text_analysis_receives_edited_timeline_not_original_audio(tmp_path, monkeypatch, kind, changed_during_analysis):
    from app import main
    from app.models import Clip, Project, Track

    rate = 44100
    source = tmp_path / 'source.wav'
    sf.write(source, np.repeat([.2, .4, .6], rate), rate)
    track = Track(id='t', name='Voice', filename='source.wav', duration_ms=3000, channels=1,
        clips_initialized=True, clips=[Clip(id='a', source_start_ms=0, source_end_ms=1000, timeline_start_ms=0),
                                      Clip(id='b', source_start_ms=2000, source_end_ms=3000, timeline_start_ms=2000)])
    project = Project(id='p', title='Edited', target='DAW', tracks=[track])
    monkeypatch.setattr(main, 'load_project', lambda _: project)
    monkeypatch.setattr(main, 'save_project', lambda _: None)
    monkeypatch.setattr(main, 'audio_path', lambda *_: source)
    monkeypatch.setattr(main, '_ai_external_engine', lambda _: True)

    def infer(worker, path, options):
        data, sr = sf.read(path, always_2d=True)
        assert sr == rate
        assert np.mean(data[rate//4:rate//2]) == pytest.approx(.2, abs=.01)
        assert np.max(np.abs(data[rate:2*rate])) < .001
        assert np.mean(data[9*rate//4:5*rate//2]) == pytest.approx(.6, abs=.01)
        if changed_during_analysis:
            track.delay_ms = 50
        if worker == 'whisper':
            return {'json': {'transcript.json': {'lines': [{'time_ms': 2100, 'text': 'after cut'}]}}}, 'job'
        return {'json': {'chords.json': {'chords': [{'time_ms': 2100, 'chord': 'C'}]}}}, 'job'

    monkeypatch.setattr(main, '_native_remote_infer', infer)
    job = 'edited-' + kind
    with main.MEDIA_JOB_LOCK:
        main.MEDIA_JOBS[job] = {'id': job, 'kind': kind, 'project_id': 'p', 'status': 'queued',
                                'progress': 0, 'message': '', 'created_at': 0, 'updated_at': 0,
                                'result': None, 'error': None}
    main._text_music_worker(job, 'p', 't', kind)
    if changed_during_analysis:
        assert main.MEDIA_JOBS[job]['status'] == 'failed'
        assert 'track changed during analysis' in main.MEDIA_JOBS[job]['error']
        assert not getattr(project, kind)
        return
    assert main.MEDIA_JOBS[job]['status'] == 'completed', main.MEDIA_JOBS[job]['error']
    assert getattr(project, kind)[0].time_ms == 2100


def test_server_ai_resamples_unsupported_source_before_worker(tmp_path, monkeypatch):
    from app import ai_global_execution, ai_metering_agent, ai_server_execution, model_license_policy
    source = tmp_path / 'source.wav'
    sf.write(source, np.zeros(16000), 16000)
    monkeypatch.setattr(ai_server_execution, 'identity', lambda: 1)
    monkeypatch.setattr(ai_global_execution, 'active_owner', lambda *args: 1)
    monkeypatch.setattr(model_license_policy, 'evaluate', lambda *args: None)
    def run(argv, **kwargs):
        result = subprocess.run(argv, capture_output=True, check=False)
        return SimpleNamespace(exit_code=result.returncode)
    monkeypatch.setattr(ai_metering_agent, 'run_supervised_process', run)
    def worker(*args, source_wav, **kwargs):
        with wave.open(io.BytesIO(source_wav), 'rb') as handle:
            assert handle.getframerate() == 44100 and handle.getnchannels() == 2
        result = io.BytesIO()
        with zipfile.ZipFile(result, 'w') as archive:
            archive.writestr('manifest.json', '{}')
            archive.writestr('transcript.json', json.dumps({'lines': []}))
        return result.getvalue(), {'job_id': 'job'}
    monkeypatch.setattr(ai_metering_agent, 'execute_registered_worker', worker)
    result, job = ai_server_execution.infer('whisper', source)
    assert job == 'job' and result['json']['transcript.json']['lines'] == []


def test_madmom_discovered_in_registered_separate_runtime(tmp_path, monkeypatch):
    from app import ai_models, ai_worker_registry
    runtime = tmp_path / 'runtime'
    venv.EnvBuilder(with_pip=False).create(runtime)
    site = runtime / 'lib' / f'python{sys.version_info.major}.{sys.version_info.minor}' / 'site-packages'
    for folder in ('madmom_infer', 'madmom_infer/features', 'madmom_infer/audio'):
        path = site / folder
        path.mkdir(parents=True, exist_ok=True)
        (path / '__init__.py').write_text('')
    (site / 'madmom_infer/features/chords.py').write_text('')
    (site / 'madmom_infer/audio/chroma.py').write_text('')
    monkeypatch.setenv('MTA_AI_UNIFIED_WORKERS_ENABLED', 'true')
    monkeypatch.setattr(ai_worker_registry, 'resolve_worker', lambda _: Path('/trusted/adapter.py'))
    monkeypatch.setattr(ai_worker_registry, 'worker_python', lambda _: str(runtime / 'bin/python'))
    assert ai_models.chord_engine_available('madmom-deep-chroma')


def test_mta_export_renders_edits_and_mixer_from_project_start(tmp_path, monkeypatch):
    from app import storage
    from app.codec import export_mta
    from app.models import Clip, Track
    from app.mta_reverse import deobfuscate_media_copy

    monkeypatch.setattr(storage, 'ROOT', (tmp_path / 'projects').resolve())
    project = storage.create_project('Edited', target='MTA16', owner_user_id=1)
    rate = 44100
    time = np.arange(rate * 3) / rate
    amplitude = np.repeat([.2, .4, .6], rate)
    source = storage.audio_path(project.id, 'voice.wav')
    sf.write(source, amplitude * np.sin(2*np.pi*440*time), rate)
    project.master_volume_db = -6
    project.tracks = [Track(id='t', name='Voice', filename='voice.wav', duration_ms=3000,
        channels=1, volume_db=-6, clips_initialized=True,
        clips=[Clip(id='a', source_start_ms=0, source_end_ms=1000, timeline_start_ms=0),
               Clip(id='b', source_start_ms=2000, source_end_ms=3000, timeline_start_ms=1000)])]
    result = tmp_path / 'result.mta'
    export_mta(project, result, profile='generic')
    canonical = tmp_path / 'result.mka'
    deobfuscate_media_copy(result, canonical)
    decoded = tmp_path / 'decoded.wav'
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(canonical), '-map', '0:a:0',
                    '-c:a', 'pcm_f32le', str(decoded)], check=True)
    audio, actual_rate = sf.read(decoded, always_2d=True)
    assert actual_rate == rate
    rms = lambda start, end: np.sqrt(np.mean(audio[int(rate*start):int(rate*end)]**2))
    # Mono-to-stereo conversion applies the standard -3 dB channel gain.
    assert rms(.1, .4) == pytest.approx(.2 * 10**(-12/20) / 2, rel=.15)
    assert rms(1.2, 1.5) / rms(.2, .5) == pytest.approx(3, rel=.1)
    assert np.max(np.abs(audio[:rate//2])) > .02


def test_editor_json_roundtrip_and_cumulative_chord_delay():
    from test_r210_decimal_bpm_shortcuts import function
    setup = r'''const assert=require('assert/strict');
let current={title:'Song'},lyricsChordsEditorLyricsDraft=[{time_ms:1000,text:'Hello',words:[{start_ms:1000,end_ms:1200,text:'Hello'}]}],lyricsChordsEditorDraft=[{time_ms:1500,end_ms:2000,chord:'C',manual_anchor:true,anchor_line_time_ms:1000}],lyricsChordsEditorSelected=-1,lyricsChordsEditorFocus=null;
let saved=null,refreshes=0;function ensureEventSnapshot(){}function refreshLyricsChordsEditor(){refreshes++}function confirm(){return true}function tr(a){return a}function toast(x){throw Error(x)}async function saveGeneratedBlob(blob,name,mime){saved={blob,name,mime}};
'''
    check = r'''(async()=>{
assert.equal(shiftChordsDraft(-500),true);assert.equal(lyricsChordsEditorDraft[0].time_ms,1000);assert.equal(lyricsChordsEditorDraft[0].end_ms,1500);assert.equal(lyricsChordsEditorDraft[0].manual_anchor,false);
assert.equal(shiftChordsDraft(-1001),false);assert.equal(lyricsChordsEditorDraft[0].time_ms,1000);
await exportLyricsChordsJson();assert.equal(saved.name,'Song.json');const doc=JSON.parse(await saved.blob.text());assert.equal(doc.lyrics[0].words[0].text,'Hello');assert.equal(doc.chords[0].time_ms,1000);
lyricsChordsEditorLyricsDraft=[];lyricsChordsEditorDraft=[];const input={files:[{size:100,text:async()=>JSON.stringify(doc)}],value:'x'};await importLyricsChordsJson(input);assert.deepEqual(lyricsChordsEditorLyricsDraft,doc.lyrics);assert.deepEqual(lyricsChordsEditorDraft,doc.chords);assert.equal(input.value,'');assert.equal(refreshes,2);
})().catch(e=>{console.error(e);process.exitCode=1});'''
    source = setup + '\n' + '\n'.join(function(name) for name in
        ('shiftChordsDraft', 'exportLyricsChordsJson', 'lyricTextGroups', 'splitImportedLyrics', 'importLyricsChordsJson')) + '\n' + check
    subprocess.run(['node', '-e', source], check=True, capture_output=True, text=True)


def test_select_all_segments_delete_and_split_selected_tracks():
    from test_r210_decimal_bpm_shortcuts import function
    setup = r'''const assert=require('assert/strict');const MtaTimelineRules=require('./app/static/timeline_rules.js');
let current={tracks:[{id:'a',delay_ms:0,clips:[{id:'a1',source_start_ms:0,source_end_ms:2000,timeline_start_ms:0}]},{id:'b',delay_ms:100,clips:[{id:'b1',source_start_ms:0,source_end_ms:2000,timeline_start_ms:0}]}]},selectedTimelineSegments=new Set(),selectedTrackIdSet=new Set(['a','b']),timelineTool='select',projectDirty=false;
let id=0,changed=0,timelineSelectionOnly=false,selectedTrackId='a';function $$(s){return []}function $(s){return null}function updateSel(){}function selectedTrackIds(){return [...selectedTrackIdSet]}function selectAllTracks(){selectedTrackIdSet=new Set(current.tracks.map(t=>t.id))}function paintSegmentSelection(){}function checkpointHistory(){}function clipId(){return 'new'+(++id)}function trackDelayMs(t){return t.delay_ms}function render(){}function markDirty(){}function toast(){}function timingAudioChanged(){changed++}function updateEditActionState(){};
'''
    check = r'''(async()=>{splitSelectedTracksAt(1000);assert.equal(current.tracks[0].clips[0].source_end_ms,1000);assert.equal(current.tracks[1].clips[0].source_end_ms,900);
selectAllTimelineSegments();assert.equal(selectedTimelineSegments.size,4);assert.equal(selectedTrackIdSet.size,0);await deleteSelection(true);assert.equal(current.tracks[0].clips.length,0);assert.equal(current.tracks[1].clips.length,0);assert.equal(changed,1);
})().catch(e=>{console.error(e);process.exitCode=1});'''
    source = setup + '\n' + '\n'.join(function(name) for name in
        ('selectAllTimelineSegments', 'selectedSegmentItems', 'splitSelectedTracksAt', 'editSelectedSegments', 'deleteSelection')) + '\n' + check
    subprocess.run(['node', '-e', source], check=True, capture_output=True, text=True)


def test_separate_lyrics_editor_preserves_word_timing_and_manual_anchors():
    from test_r210_decimal_bpm_shortcuts import function
    setup = r'''const assert=require('assert/strict');
const row={dataset:{originalIndex:'0'},querySelector(s){return {value:{'.timed-start':'1.500','.timed-end':'2.500','.timed-value':'Hello'}[s]}}};
const document={querySelectorAll:()=>[row]};let current={lyrics:[{time_ms:1000,end_ms:2000,text:'Hello',words:[{text:'Hello',start_ms:1100,end_ms:1900,syllables:[{text:'Hel',start_ms:1100,end_ms:1400}]}]}],chords:[{manual_anchor:true,anchor_line_time_ms:1000}],markers:[{manual_lyric_anchor:true,anchor_lyric_time_ms:1000}]};
function ensureEventSnapshot(){}function render(){}function markDirty(){}function closeUtilityModal(){}function toast(){}
'''
    check = r'''saveTimedEditor('lyrics');assert.equal(current.lyrics[0].time_ms,1500);assert.equal(current.lyrics[0].words[0].start_ms,1600);assert.equal(current.lyrics[0].words[0].syllables[0].end_ms,1900);assert.equal(current.chords[0].anchor_line_time_ms,1500);assert.equal(current.markers[0].anchor_lyric_time_ms,1500);'''
    source = setup + '\n' + '\n'.join(function(name) for name in
        ('timedEditorConfig', 'parseTimedEditorTime', 'shiftTimedLyricsAnchors', 'saveTimedEditor')) + '\n' + check
    subprocess.run(['node', '-e', source], check=True, capture_output=True, text=True)
