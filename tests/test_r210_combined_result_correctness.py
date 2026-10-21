"""Synthetic contract regressions, not neural accuracy tests."""
import json
import pytest
from app.models import MidiNote, MidiControl
from app.music_interchange import MusicResult, MusicPart, no_notes
from app.music_reconciliation import reconcile
from app.studio_midi_benchmark import evaluate_files
from app.music_channels import route_parts
from app.studio_multitrack import transcribe_separated


def score(program=0, channel=0, drums=False):
    return MusicResult(parts=[MusicPart(id='part',name='Model part',program=program,percussion=drums,
        notes=[MidiNote(id='note',pitch=60,start_ms=0,duration_ms=200,channel=channel)],
        controls=[MidiControl(time_ms=0,data=[0xB0|channel,64,0])])])


def test_all_empty_preserves_region_and_warnings():
    a=no_notes(['a']).model_copy(update={'offset_ms':300})
    b=no_notes(['b']).model_copy(update={'offset_ms':300})
    result,report=reconcile([('a',a.model_dump()),('b',b.model_dump())])
    assert not result.parts and result.offset_ms==300
    assert {'a','b'}<=set(result.warnings)
    assert report['empty_models']==['a','b']


def test_empty_preferred_promotes_actual_model():
    secondary=score()
    result,report=reconcile([('silent',no_notes(['Silent preferred model'])),('second',secondary),('third',score())])
    assert sum(bool(p.notes) for p in result.parts)==1 and report['primary_model']=='second'
    assert report['primary_audit']['notes_supported_by_other_model']==1
    assert report['empty_models']==['silent'] and len(result.alternatives)==2
    assert 'Silent preferred model' in result.warnings and secondary.parts[0].id=='part'


def test_benchmark_valid_no_notes_protocol(tmp_path):
    ref=tmp_path/'reference.json';pred=tmp_path/'prediction.json'
    ref.write_text(score().model_dump_json());pred.write_text(no_notes().model_dump_json())
    report=evaluate_files(ref,pred)
    assert report['predicted_notes']==report['matched_notes']==0
    assert report['reference_notes']==1 and report['recall']==report['f1']==0
    assert report['by_instrument'][0]['false_negatives']==1
    assert evaluate_files(pred,pred)['reference_notes']==0
    pred.write_text(json.dumps({'parts':[]}))
    with pytest.raises(ValueError):evaluate_files(ref,pred)


def test_routing_notes_and_controllers_without_mutation():
    parts=[score(0).parts[0],score(24).parts[0],score(None,3,True).parts[0]]
    routed,warnings=route_parts(parts)
    assert [p.notes[0].channel for p in routed]==[0,1,9]
    assert [p.controls[0].data[0] for p in routed]==[0xB0,0xB1,0xB9]
    assert not warnings
    assert parts[1].notes[0].channel==0 and parts[2].notes[0].channel==3
    assert [p.program for p in routed]==[0,24,None]


def test_distinct_channel_streams_and_payload():
    p=score().parts[0];p.notes.append(p.notes[0].model_copy(update={'id':'other','channel':2}))
    p.controls.extend([MidiControl(time_ms=10,data=[0xC2,40]),MidiControl(time_ms=20,data=[0xE2,1,70])])
    routed,_=route_parts([p])
    assert [n.channel for n in routed[0].notes]==[0,1]
    assert [c.data for c in routed[0].controls]==[[0xB0,64,0],[0xC1,40],[0xE1,1,70]]


def test_channel_capacity_retains_parts_with_warning():
    routed,warnings=route_parts([score(i).parts[0] for i in range(16)])
    assert len(routed)==16 and len(warnings)==1 and 'reused' in warnings[0]
    assert [p.notes[0].channel for p in routed][:15]==[c for c in range(16) if c!=9]
    assert routed[-1].notes[0].channel==0


def test_deep_unique_channels_and_original_alternatives():
    def compute(user,kind,plan,**kwargs):
        return ({'stem_'+label+'.wav':label.encode() for label in ('bass','drums','other','vocals')}
                if kind=='demucs' else score()),{}
    result,_=transcribe_separated(0,b'audio',{},cancelled=lambda:False,timeout=20,compute=compute)
    assert len({p.notes[0].channel for p in result.parts if p.notes})==4
    assert all(p.notes[0].channel==0 for p in result.alternatives)


def test_deep_cancel_during_last_worker():
    cancelled=False;calls=[]
    def compute(user,kind,plan,**kwargs):
        nonlocal cancelled
        calls.append(kind)
        if len(calls)==8:cancelled=True
        return ({'stem_'+label+'.wav':label.encode() for label in ('bass','drums','other','vocals')}
                if kind=='demucs' else score()),{}
    with pytest.raises(RuntimeError,match='result discarded'):
        transcribe_separated(0,b'audio',{},cancelled=lambda:cancelled,timeout=20,compute=compute)
    assert len(calls)==8


@pytest.mark.parametrize('start,end,duration,expected',[
    (0.,1.,2.,(0.,1.)),(-.1,1.,2.,(0.,1.)),(1.,3.,2.,(1.,2.)),
    (2.,3.,2.,None),(-2.,-1.,2.,None),(1.,1.,2.,None),
])
def test_model_padding_is_bounded(start,end,duration,expected):
    from app.transcription_timing import bound_interval
    assert bound_interval(start,end,duration)==expected


@pytest.mark.parametrize('start,end,duration',[(float('nan'),1,2),(0,float('inf'),2),(0,1,0)])
def test_nonfinite_model_timing_fails(start,end,duration):
    from app.transcription_timing import bound_interval
    with pytest.raises(ValueError):bound_interval(start,end,duration)


def test_benchmark_voice_class_does_not_count_as_generated_gm_proxy():
    from app.studio_midi_benchmark import evaluate
    voice=score(53);voice.parts[0].instrument='singing-voice'
    synth=score(53)
    assert evaluate(voice,synth)['matched_notes']==0
    assert evaluate(voice,voice)['matched_notes']==1
