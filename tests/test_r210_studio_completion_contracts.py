"""Explicit model-contract/PCM fixtures; these tests do not certify neural inference."""
from pathlib import Path
import sys
import pytest
import numpy as np
import soundfile as sf
from app.music_interchange import MusicResult,MusicPart,no_notes,parse_result
from app.models import MidiNote


def music():return MusicResult(parts=[MusicPart(id='p',name='Piano',program=0,notes=[MidiNote(id='n',pitch=60,start_ms=0,duration_ms=500)])])


def test_empty_results_preserve_strict_score_schema():
    with pytest.raises(ValueError):MusicResult(parts=[])
    empty=parse_result(no_notes().model_dump_json());assert not empty.parts and empty.empty_reason=='no-notes'
    from app.music_reconciliation import reconcile
    result,report=reconcile([('a',empty),('b',music())]);assert result.parts and not report['calibrated_confidence']
    result,report=reconcile([('a',empty),('b',empty)]);assert not result.parts and not report['comparisons']


def test_completed_stage_recovers_without_execution_or_double_usage(tmp_path):
    from app.studio_stage_cache import StageCache
    calls=[];ack=[]
    def compute(*args,**kwargs):
        calls.append(args);return music(),{'usage':{'cpu_seconds':4},'acknowledge':lambda:ack.append(bool(list((tmp_path/'one').glob('*.zip'))))}
    first=StageCache(tmp_path/'one',dependency=lambda *a:'epoch1')
    result,meta=first.execute(compute,1,'audio-to-midi-yourmt3',{},audio=b'audio')
    assert ack==[True] and meta['usage']['cpu_seconds']==4
    second=StageCache(tmp_path/'two',tmp_path/'one',dependency=lambda *a:'epoch1')
    replay,meta=second.execute(compute,1,'audio-to-midi-yourmt3',{},audio=b'audio')
    assert replay==result and meta['usage']=={} and meta['recovered'] and len(calls)==1
    changed=StageCache(tmp_path/'three',tmp_path/'one',dependency=lambda *a:'epoch2')
    changed.execute(compute,1,'audio-to-midi-yourmt3',{},audio=b'audio');assert len(calls)==2


def test_same_stage_cache_object_invalidates_when_runtime_changes(tmp_path):
    from app.studio_stage_cache import StageCache
    epoch=['runtime-A'];calls=[]
    cache=StageCache(tmp_path,dependency=lambda *a:epoch[0])
    def compute(*args,**kwargs):
        calls.append(epoch[0]);return no_notes(),{'usage':{'cpu_seconds':1}}
    cache.execute(compute,1,'audio-to-midi',{},audio=b'audio')
    replay,meta=cache.execute(compute,1,'audio-to-midi',{},audio=b'audio')
    assert meta['recovered'] and not replay.parts and calls==['runtime-A']
    epoch[0]='runtime-B'
    _,meta=cache.execute(compute,1,'audio-to-midi',{},audio=b'audio')
    assert not meta.get('recovered') and calls==['runtime-A','runtime-B']
    assert len(list(tmp_path.glob('*.zip')))==2


def test_corrupt_stage_is_recomputed_but_links_are_rejected(tmp_path):
    from app.studio_stage_cache import StageCache
    cache=StageCache(tmp_path,dependency=lambda *a:'epoch')
    def compute(*a,**k):return no_notes(),{'usage':{}}
    cache.execute(compute,1,'audio-to-midi',{},audio=b'a')
    file=next(tmp_path.glob('*.zip'));file.write_bytes(b'corrupted')
    assert not cache.execute(compute,1,'audio-to-midi',{},audio=b'a')[0].parts
    file.unlink();outside=tmp_path/'outside';outside.write_bytes(b'private');file.symlink_to(outside)
    with pytest.raises(ValueError,match='link'):cache.execute(compute,1,'audio-to-midi',{},audio=b'a')


def test_schema_invalid_checkpoint_recomputes_real_stage(tmp_path):
    import hashlib
    import json
    import zipfile
    from app.studio_stage_cache import StageCache
    cache = StageCache(tmp_path, dependency=lambda *a: 'epoch')
    calls = []
    def compute(*args, **kwargs):
        calls.append(True)
        return no_notes(), {'usage': {'cpu_seconds': 1}}
    plan = {}
    key = cache.key('audio-to-midi', plan, b'audio', 'music')
    payload = b'{"parts": "invalid-not-a-list"}'
    receipt = {'schema': 'mta-studio-stage-1', 'key': key,
               'sha256': hashlib.sha256(payload).hexdigest()}
    with zipfile.ZipFile(tmp_path / (key + '.zip'), 'w') as archive:
        archive.writestr('receipt.json', json.dumps(receipt))
        archive.writestr('result', payload)
    result, meta = cache.execute(compute, 1, 'audio-to-midi', plan, audio=b'audio')
    assert len(calls) == 1 and not meta.get('recovered') and not result.parts
    replay, receipt = cache.execute(compute, 1, 'audio-to-midi', plan, audio=b'audio')
    assert len(calls) == 1 and receipt['recovered'] and not replay.parts


def test_invalid_computed_music_is_not_persisted_or_acknowledged(tmp_path):
    from app.studio_stage_cache import StageCache
    from pydantic import ValidationError
    cache = StageCache(tmp_path, dependency=lambda *a: 'epoch')
    acknowledgements = []

    class InvalidResult:
        def model_dump_json(self):
            return '{"protocol":"mta-music-1","parts":[]}'

    def compute(*args, **kwargs):
        return InvalidResult(), {'usage': {'cpu_seconds': 1},
                                 'acknowledge': lambda: acknowledgements.append(True)}

    with pytest.raises(ValidationError):
        cache.execute(compute, 1, 'audio-to-midi', {}, audio=b'audio')
    assert not acknowledgements
    assert not list(tmp_path.glob('*.zip'))


def test_failed_stage_is_never_cached(tmp_path):
    from app.studio_stage_cache import StageCache
    cache=StageCache(tmp_path,dependency=lambda *a:'epoch')
    def fail(*a,**k):raise RuntimeError('model failure')
    with pytest.raises(RuntimeError):cache.execute(fail,1,'audio-to-midi',{},audio=b'a')
    assert not list(tmp_path.glob('*.zip'))


def fake_conversion(tmp_path,kind='seed-vc'):
    bindings={'runtime_root':'runtime','script':'runtime/inference.py','checkpoint':'model.pt','config':'config.yml','reference':'ref.wav','hf_home':'cache'}
    if kind=='rvc':bindings.pop('reference');bindings.pop('hf_home');bindings.pop('config')
    (tmp_path/'runtime').mkdir(exist_ok=True)
    if kind=='seed-vc':
        (tmp_path/'config.yml').write_text('preprocess_params:\n  sr: 44100\nmodel_params:\n  DiT:\n    f0_condition: true\n  length_regulator:\n    f0_condition: true\n')
    return {'id':'fixture','name':'Fixture','kind':kind,'folder':tmp_path,'bindings':bindings,
            'files':{'model.pt':{'sha256':'a'*64}}}


@pytest.mark.parametrize('kind',['seed-vc','rvc'])
def test_conversion_real_pcm_io_and_exact_model_arguments(tmp_path,monkeypatch,kind):
    from app import vocal_conversion as vc
    value=fake_conversion(tmp_path,kind)
    monkeypatch.setattr('app.studio_asset_registry.runtime',lambda *a,**k:(value,Path(sys.executable)))
    source=tmp_path/'voice.wav';sf.write(source,np.full(24000,.1,dtype='float32'),48000,subtype='PCM_24')
    def inference(argv,**kwargs):
        assert Path(argv[1]).name==('seed_vc_runner.py' if kind=='seed-vc' else 'studio_offline_runner.py')
        assert kwargs['env']['HF_HUB_OFFLINE']=='1'
        if kind=='seed-vc':
            assert argv[argv.index('--f0-condition')+1]=='True' and argv[argv.index('--length-adjust')+1]=='1.0'
            out=Path(argv[argv.index('--output')+1])/'converted.wav'
        else:
            assert argv[argv.index('--f0-method')+1]=='rmvpe'
            out=Path(argv[argv.index('--output')+1])
        sf.write(out,np.full(22050,.2,dtype='float32'),44100,subtype='PCM_24')
    monkeypatch.setattr(vc.subprocess,'run',inference)
    receipt=vc.convert(source,{'asset_id':'fixture','mix':.5,'index_rate':0})
    audio,rate=sf.read(source);assert rate==48000 and len(audio)==24000
    assert np.mean(audio[100:-100])==pytest.approx(.15,abs=1e-4)
    assert receipt['backend']==kind and not receipt['musical_quality_validated']


def test_conversion_failure_never_replaces_original_audio(tmp_path,monkeypatch):
    from app import vocal_conversion as vc
    value=fake_conversion(tmp_path);monkeypatch.setattr('app.studio_asset_registry.runtime',lambda *a,**k:(value,Path(sys.executable)))
    source=tmp_path/'voice.wav';sf.write(source,np.full(24000,.1,dtype='float32'),48000,subtype='PCM_24');before=source.read_bytes()
    def bad(argv,**kwargs):sf.write(Path(argv[argv.index('--output')+1])/'bad.wav',np.zeros(80000),48000)
    monkeypatch.setattr(vc.subprocess,'run',bad)
    with pytest.raises(ValueError,match='synchronization'):vc.convert(source,{'asset_id':'fixture'})
    assert source.read_bytes()==before


def test_transkun_contract_reads_actual_midi_velocity_and_sustain(tmp_path,monkeypatch):
    import mido
    from app import transkun_adapter as tk
    value={'id':'piano','kind':'transkun','folder':tmp_path,'bindings':{'runtime_root':'runtime','checkpoint':'model.pt','config':'config.conf'},'files':{'model.pt':{'sha256':'a'*64},'config.conf':{'sha256':'b'*64}}}
    monkeypatch.setattr('app.studio_asset_registry.runtime',lambda *a,**k:(value,Path(sys.executable)))
    source=tmp_path/'piano.wav';sf.write(source,np.zeros(48000),48000)
    def inference(argv,**kwargs):
        assert 'transkun_runner.py' in argv[1] and '--checkpoint' in argv and '--config' in argv
        assert argv[argv.index('--checkpoint-sha256')+1]=='a'*64
        assert argv[argv.index('--config-sha256')+1]=='b'*64
        midi=mido.MidiFile();track=mido.MidiTrack();midi.tracks.append(track)
        track.extend([mido.Message('note_on',note=60,velocity=85,time=0),mido.Message('control_change',control=64,value=127,time=0),mido.Message('note_off',note=60,velocity=0,time=480)])
        midi.save(argv[argv.index('--output')+1])
    monkeypatch.setattr(tk.subprocess,'run',inference)
    result=tk.transcribe(source,{'asset_id':'piano','name':'Fixture'})
    assert result.parts[0].program==0 and result.parts[0].notes[0].velocity==85
    assert result.parts[0].notes[0].duration_ms==500 and result.parts[0].controls[0].data==[176,64,127]


def test_text_alignment_melismas_word_ids_and_missing_count(monkeypatch):
    from app.vocal_phonemizer import phonemize_score,word_regions
    monkeypatch.setattr('app.vocal_phonemizer.ipa_for_text',lambda *a:'lˈa')
    profile={'language':'it','inventory':['SP','l','a'],'vowels':['a'],'ipa_map':{'l':['l'],'a':['a']}}
    request={'language':'it','lyric_text':'la la','melisma_counts':[1,2],
             'notes':[{'id':f'n{i}','pitch':60,'start_ms':i*500,'duration_ms':500,'syllable':'A'} for i in range(3)]}
    result=phonemize_score(request,profile)
    assert result['notes'][2]['phonemes']==['a']
    words=word_regions(result['notes']);assert len(words)==2 and words[1][6]==[2] and words[1][7]==['n1','n2']
    with pytest.raises(ValueError,match='syllable count'):phonemize_score({**request,'melisma_counts':[]},profile)


def test_dynamic_curves_reach_f0_dynamics_and_neural_inputs():
    from app.vocal_expression import f0_curve,apply_dynamics,Expression
    from app.diffsinger_bridge import ds_from_request
    notes=[{'pitch':69,'start_ms':0,'duration_ms':1000,'velocity':127,'syllable':'a'}]
    settings={'attack_ms':0,'release_ms':0,'curves':{'pitch_cents':[{'time_ms':0,'value':0},{'time_ms':1000,'value':1200}],
        'dynamics':[{'time_ms':0,'value':0},{'time_ms':1000,'value':1}],
        'energy':[{'time_ms':0,'value':-40},{'time_ms':1000,'value':-20}]}}
    curve=f0_curve(notes,settings);assert curve[100]==pytest.approx(440*2**.5)
    audio=apply_dynamics(np.ones(48000),48000,notes,settings)
    assert audio[0]==0 and audio[24000]==pytest.approx(.5)
    ds=ds_from_request({'notes':notes,'expression':settings});assert float(ds['energy'].split()[100])==pytest.approx(-30)
    with pytest.raises(ValueError):Expression(curves={'dynamics':[{'time_ms':1,'value':0},{'time_ms':1,'value':1}]})


def test_offline_runner_blocks_python_network_downloads(tmp_path):
    import subprocess
    script=tmp_path/'download.py';script.write_text("import socket\nsocket.create_connection(('example.com',443),timeout=1)\n")
    result=subprocess.run([sys.executable,'app/studio_offline_runner.py',str(script)],capture_output=True,text=True)
    assert result.returncode!=0 and 'inference is offline' in result.stderr
