import pytest
from app import main


@pytest.mark.parametrize('names',[
    ['backing_vocals.wav','lead_vocals.wav'],
    ['lead_vocals.wav','backing_vocals.wav'],
    ['instrumental.wav','vocals.wav'],
])
def test_backing_filename_cannot_be_selected_as_lead(tmp_path,monkeypatch,names):
    monkeypatch.setattr(main,'_ai_external_engine',lambda kind:True)
    audio={name:(b'backing' if name.startswith(('back','instrument')) else b'lead') for name in names}
    monkeypatch.setattr(main,'_native_remote_infer',lambda *args:({'audio':audio},'test-job'))
    lead,backing,method=main._split_lead_backing_vocals(tmp_path/'source.wav',tmp_path/'out')
    assert lead.read_bytes()==b'lead' and backing.read_bytes()==b'backing'
    assert method=='remote:test-job'


def test_identical_silent_artifact_bytes_do_not_imply_missing_stem(tmp_path,monkeypatch):
    monkeypatch.setattr(main,'_ai_external_engine',lambda kind:True)
    audio={'first.wav':b'silence','second.wav':b'silence'}
    monkeypatch.setattr(main,'_native_remote_infer',lambda *args:({'audio':audio},'test-job'))
    lead,backing,_=main._split_lead_backing_vocals(tmp_path/'source.wav',tmp_path/'out')
    assert lead!=backing and lead.read_bytes()==backing.read_bytes()==b'silence'
