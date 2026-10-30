"""Runtime/decoder contracts only; synthetic tokens are not neural accuracy tests."""
from types import SimpleNamespace
import hashlib
import json
import pytest
from app import mrmt3_adapter as adapter
from app.mrmt3_decode import decode
from app.mrmt3_checkpoint import convert


class Codec:
    steps_per_second=100
    def decode_event_index(self,index):
        rows={0:('tie',0),1:('velocity',1),2:('velocity',0),3:('pitch',60),
              4:('shift',10),5:('program',9),6:('drum',60),7:('program',0),8:('shift',30)}
        if index not in rows:raise ValueError('Invalid token')
        kind,value=rows[index];return SimpleNamespace(type=kind,value=value)


def test_program_nine_is_not_drum_and_drum_duration_is_explicit():
    notes,audit=decode([{'start_time':0.,'est_tokens':[0,5,1,3,6,4,2,3]}],Codec(),1.)
    assert len(notes)==2 and not audit['invalid_events']
    melodic=next(n for n in notes if not n['is_drum']);drum=next(n for n in notes if n['is_drum'])
    assert melodic['program']==9 and melodic['end_time']==.1
    assert drum['program']==0 and drum['end_time']==.01


def test_ties_preserve_note_across_windows_without_duplicates():
    rows=[{'start_time':0.,'est_tokens':[0,1,3,4]},
          {'start_time':.2,'est_tokens':[3,0,4,2,3]}]
    notes,audit=decode(rows,Codec(),1.)
    assert len(notes)==1 and notes[0]['start_time']==0. and notes[0]['end_time']==pytest.approx(.3)
    assert audit['invalid_events']==0


def test_untied_notes_close_at_next_source_window():
    notes,_=decode([{'start_time':0.,'est_tokens':[0,1,3]},
                    {'start_time':.2,'est_tokens':[0]}],Codec(),1.)
    assert len(notes)==1 and notes[0]['end_time']==.2


def test_invalid_and_outside_window_events_are_audited_not_invented():
    notes,audit=decode([{'start_time':0.,'est_tokens':[0,999,1,8,3]}],Codec(),.2)
    assert not notes and audit['invalid_events']==1 and audit['dropped_events']==1
    with pytest.raises(ValueError):decode([{'start_time':float('nan'),'est_tokens':[]}],Codec(),1.)
    with pytest.raises(ValueError):decode([{'start_time':.2,'est_tokens':[]},{'start_time':.1,'est_tokens':[]}],Codec(),1.)


def test_no_configured_runtime_is_unavailable(monkeypatch):
    monkeypatch.delenv('MTA_STUDIO_MRMT3_RUNTIME',raising=False)
    assert adapter.python_for() is None


def runtime(tmp_path,monkeypatch,tested=True):
    monkeypatch.setenv('MTA_STUDIO_MRMT3_RUNTIME',str(tmp_path))
    files={}
    for name in sorted(adapter.REQUIRED):
        p=tmp_path/name;p.parent.mkdir(exist_ok=True,parents=True);p.write_bytes(b'contract file')
        files[name]=hashlib.sha256(p.read_bytes()).hexdigest()
    # Synthetic runtime/decoder fixture: inject a deployment-owned source
    # contract independently from the receipt, never a production bypass.
    monkeypatch.setattr('app.transcription_source_contract.profile',lambda family:{
        'files':{n:h for n,h in files.items() if n!=adapter.WEIGHTS},'import_roots':['source'],
        'checkpoints':{adapter.MODEL:{adapter.WEIGHTS:files[adapter.WEIGHTS]}}})
    python=tmp_path/'bin/python';python.parent.mkdir();python.write_bytes(b'test interpreter identity')
    value={'schema':'mta-mrmt3-runtime-1','model':adapter.MODEL,'source_commit':adapter.SOURCE_COMMIT,
           'tested':tested,'files':files,'python_sha256':hashlib.sha256(python.read_bytes()).hexdigest()}
    receipt=tmp_path/'mta-runtime.json';receipt.write_text(json.dumps(value));return receipt,value,python


def test_runtime_requires_actual_tested_receipt_and_pinned_identity(tmp_path,monkeypatch):
    receipt,value,python=runtime(tmp_path,monkeypatch,False)
    assert adapter.python_for() is None
    value['tested']=True;receipt.write_text(json.dumps(value))
    assert adapter.python_for()==python and adapter.verified_runtime()[0]==tmp_path
    value['source_commit']='0'*40;receipt.write_text(json.dumps(value))
    assert adapter.python_for() is None


def test_full_runtime_hash_and_path_checks(tmp_path,monkeypatch):
    receipt,value,_=runtime(tmp_path,monkeypatch)
    (tmp_path/adapter.WEIGHTS).write_bytes(b'changed')
    with pytest.raises(ValueError,match='integrity'):adapter.verified_runtime()
    value['files']['../escape']='a'*64;receipt.write_text(json.dumps(value))
    assert adapter.python_for() is None


def test_checkpoint_unknown_bytes_rejected_before_deserialization(tmp_path):
    p=tmp_path/'weights.pth';p.write_bytes(b'not a reviewed model')
    with pytest.raises(ValueError,match='size'):convert(p,tmp_path/'out.safetensors')
    assert not (tmp_path/'out.safetensors').exists()


def test_manual_program_override_cannot_relabel_model_output(tmp_path):
    with pytest.raises(ValueError,match='classifies'):adapter.transcribe(tmp_path/'missing.wav',{'program':0})


def test_required_source_omission_cannot_be_hidden_by_extra_inventory_files(tmp_path,monkeypatch):
    receipt,value,_=runtime(tmp_path,monkeypatch)
    value['files'].pop('source/mt3_infer/adapters/mr_mt3.py')
    receipt.write_text(json.dumps(value))
    assert adapter.python_for() is None
