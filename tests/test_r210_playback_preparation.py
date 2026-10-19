"""Real JS scheduler/cache checks and atomic preview reuse regressions."""
from pathlib import Path
import subprocess
import wave
import pytest
from test_r210_cpp_audio_engine import compiled_core  # noqa: F401

from app import preview_publish as preview

ROOT=Path(__file__).resolve().parents[1]


def test_dry_clip_schedule_negative_delay_seek_empty_and_gaps():
    script=(ROOT/'app/static/playback_prep.js').read_text()+'''
const assert=require('assert'),{clipPlan}=MtaPlaybackPrep;
const t={delay_ms:-500,clips_initialized:true,clips:[{timeline_start_ms:0,source_start_ms:1000,source_end_ms:3000},{timeline_start_ms:5000,source_start_ms:4000,source_end_ms:6000}]};
assert.deepStrictEqual(clipPlan(t,10,0),[{when:0,offset:1.5,duration:1.5},{when:4.5,offset:4,duration:2}]);
assert.deepStrictEqual(clipPlan(t,10,5),[{when:0,offset:4.5,duration:1.5}]);
assert.deepStrictEqual(clipPlan({clips_initialized:true,clips:[]},10,0),[]);
assert.deepStrictEqual(clipPlan({delay_ms:500},10,0),[{when:.5,offset:0,duration:10}]);
'''
    subprocess.run(['node','-e',script],check=True,timeout=15)


def test_cache_deduplicates_limits_ram_retries_failure_and_bounds_parallelism():
    script=(ROOT/'app/static/playback_prep.js').read_text()+'''
const assert=require('assert'),{BufferCache,mapLimit}=MtaPlaybackPrep;
(async()=>{const cache=new BufferCache(32);let calls=0;
const make=async()=>{calls++;await new Promise(r=>setTimeout(r,5));return {length:4,numberOfChannels:2}};
const [a,b]=await Promise.all([cache.get('one',make),cache.get('one',make)]);assert.strictEqual(a,b);assert.equal(calls,1);
await cache.get('two',make);assert.equal(cache.bytes,32);assert.deepStrictEqual([...cache.keys()],['two']);
let failures=0;const fail=async()=>{failures++;throw Error('bad')};for(let n=0;n<2;n++)await assert.rejects(cache.get('bad',fail));assert.equal(failures,2);
let running=0,max=0;const out=await mapLimit([1,2,3,4,5],2,async x=>{max=Math.max(max,++running);await new Promise(r=>setTimeout(r,10));running--;return x*2});assert.equal(max,2);assert.deepStrictEqual(out,[2,4,6,8,10]);
cache.clear();assert.equal(cache.bytes,0);
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    subprocess.run(['node','-e',script],check=True,timeout=15)


def test_float_wav_previews_are_valid_and_published_only_once(tmp_path):
    import numpy as np
    import soundfile as sf
    path=tmp_path/'float.wav';calls=[]
    def render(out):
        calls.append(out)
        sf.write(out,np.zeros((400,2)),44100,subtype='FLOAT')
    assert preview.publish_wav_preview(path,render)
    assert not preview.publish_wav_preview(path,render)
    assert len(calls)==1 and preview._valid_wav(path)


def test_source_reads_do_not_invalidate_cache_but_replacement_does(tmp_path):
    path=tmp_path/'audio.wav';path.write_bytes(b'123')
    before=preview.source_identity(path)
    path.read_bytes();assert preview.source_identity(path)==before
    newer=tmp_path/'new.wav';newer.write_bytes(b'123');newer.replace(path)
    assert preview.source_identity(path)!=before


def test_master_preview_reuses_cache_and_invalidates_source_and_engine(tmp_path,monkeypatch):
    from app import main,storage,audio_backend
    from app.models import Project,Track
    monkeypatch.setattr(storage,'ROOT',tmp_path/'projects')
    project=Project(id='123abc123abc',title='cache',tracks=[Track(id='a',name='a',filename='a.wav',duration_ms=100)])
    source=storage.audio_path(project.id,'a.wav');source.parent.mkdir(parents=True)
    with wave.open(str(source),'wb') as out:out.setparams((1,2,44100,0,'NONE','not compressed'));out.writeframes(b'\x00\x00'*4410)
    monkeypatch.setattr(main,'_project_for_actor',lambda *_:project)
    monkeypatch.setattr(main,'validate_project_files',lambda *_:None)
    calls=[]
    def render(p,resolver,out,**kwargs):
        calls.append(out)
        out.write_bytes(source.read_bytes())
    monkeypatch.setattr(main,'render_mix',render)
    first=main.preview_mix(project.id,None,format='wav');second=main.preview_mix(project.id,None,format='wav')
    assert first.path==second.path and len(calls)==1
    source.write_bytes(source.read_bytes()+b'\x00\x00')
    main.preview_mix(project.id,None,format='wav');assert len(calls)==2
    monkeypatch.setattr(audio_backend,'identity',lambda:'changed-test-engine')
    main.preview_mix(project.id,None,format='wav');assert len(calls)==3


def test_live_sources_skip_render_for_seekable_compatible_media(tmp_path,monkeypatch):
    import numpy as np
    import soundfile as sf
    from app import live_sources,audio_engine
    from app.models import Project,Track,Clip
    source=tmp_path/'source.wav';sf.write(source,np.full((48000,2),.1),48000,subtype='FLOAT')
    project=Project(id='raw',title='Live',sample_rate=48000,tracks=[Track(id='raw-track',name='edited',filename='source.wav',channels=2,duration_ms=1000,delay_ms=200,clips=[Clip(id='clip',timeline_start_ms=100,source_start_ms=200,source_end_ms=800)])])
    monkeypatch.setattr(audio_engine,'render_track',lambda *_a,**_k:pytest.fail('Compatible audio must not be fully rendered'))
    paths,raw=live_sources.prepare(project,[source],tmp_path)
    assert paths==[source] and raw==['raw-track']


def test_raw_cpp_blocks_match_rendered_clip_delay_and_input_gain(tmp_path,monkeypatch,request):
    binary=request.getfixturevalue("compiled_core")
    import numpy as np
    import soundfile as sf
    from app import cpp_audio,audio_engine
    from app.models import Project,Track,Clip
    from app.vst3_live_graph import Graph
    monkeypatch.setenv('MTA_AUDIO_CORE_PATH',str(binary));cpp_audio._load.cache_clear()
    source=tmp_path/'source.wav';values=np.sin(np.arange(96000,dtype=np.float32)*.07)*.1
    sf.write(source,np.column_stack((values,values)),48000,subtype='FLOAT')
    track=Track(id='raw',name='edited',filename='source.wav',duration_ms=2000,channels=2,sample_rate=48000,gain_db=-6,delay_ms=-250,clips=[Clip(id='a',source_start_ms=200,source_end_ms=900),Clip(id='b',timeline_start_ms=1200,source_start_ms=1000,source_end_ms=1600)])
    rendered=tmp_path/'rendered.wav';audio_engine.render_track(track,source,rendered,apply_inserts=False,sample_rate=48000)
    expected,rate=sf.read(rendered,always_2d=True,dtype='float32')
    project=Project(id='rawproject',title='Raw',sample_rate=48000,tracks=[track])
    graph=Graph(project,[source],raw_sources=['raw'])
    try:
        blocks=graph.raw_source(graph.readers[0],track);parts=[]
        while sum(len(x) for x in parts)<len(expected):parts.append(next(blocks))
        actual=np.concatenate(parts)[:len(expected)]
        np.testing.assert_allclose(actual,expected,atol=1e-6)
    finally:graph.close()


def test_real_isolated_cpp_stream_starts_from_raw_source_and_seeks(tmp_path,monkeypatch,request):
    import numpy as np
    import soundfile as sf
    from app.models import Project,Track,Clip
    from app.vst3_live import Session
    binary=request.getfixturevalue('compiled_core')
    monkeypatch.setenv('MTA_AUDIO_CORE_PATH',str(binary))
    source=tmp_path/'raw.wav';sf.write(source,np.full((48000*4,2),.1,dtype=np.float32),48000,subtype='FLOAT')
    track=Track(id='raw',name='raw',filename='raw.wav',duration_ms=4000,channels=2,delay_ms=500,clips=[Clip(id='c',source_end_ms=4000)])
    project=Project(id='raw-session',title='Streaming',sample_rate=48000,tracks=[track])
    session=Session(project,[source],0,_test_null=True,paused=True,raw_sources=['raw'])
    try:
        assert session.status()['active'] and not session.status()['physical']
        session.control('seek',1000)
        assert abs(session.status()['position_ms']-1000)<2
        session.control('play',0);session.control('pause',0)
        assert not session.status().get('failed')
    finally:session.close()
