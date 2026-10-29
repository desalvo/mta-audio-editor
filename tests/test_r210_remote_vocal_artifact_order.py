import pytest
from app import main


@pytest.mark.parametrize('names',[
    ['backing_vocals.wav','lead_vocals.wav'],
    ['lead_vocals.wav','backing_vocals.wav'],
    ['instrumental.wav','vocals.wav'],
])
def test_backing_filename_cannot_be_selected_as_lead(tmp_path,monkeypatch,names,reviewed_backing_policy):
    monkeypatch.setattr(main,'_ai_external_engine',lambda kind:True)
    audio={name:(b'backing' if name.startswith(('back','instrument')) else b'lead') for name in names}
    monkeypatch.setattr(main,'_native_remote_infer',lambda *args:({'audio':audio},'test-job'))
    lead,backing,method=main._split_lead_backing_vocals(tmp_path/'source.wav',tmp_path/'out',model_id='uvr_mdxnet_kara_2')
    assert lead.read_bytes()==b'lead' and backing.read_bytes()==b'backing'
    assert method=='remote:test-job'


def test_identical_silent_artifact_bytes_do_not_imply_missing_stem(tmp_path,monkeypatch,reviewed_backing_policy):
    monkeypatch.setattr(main,'_ai_external_engine',lambda kind:True)
    audio={'first.wav':b'silence','second.wav':b'silence'}
    monkeypatch.setattr(main,'_native_remote_infer',lambda *args:({'audio':audio},'test-job'))
    lead,backing,_=main._split_lead_backing_vocals(tmp_path/'source.wav',tmp_path/'out',model_id='uvr_mdxnet_kara_2')
    assert lead!=backing and lead.read_bytes()==backing.read_bytes()==b'silence'


@pytest.mark.parametrize('policy_bytes', ['{}', '{"uvr-kara-2":{"mode":"disabled"}}', '{'])
def test_unreviewed_remote_split_is_denied_before_transport_or_output(
        tmp_path,monkeypatch,reviewed_backing_policy,policy_bytes):
    from app.model_license_policy import LicenseDenied
    import json
    reviewed_backing_policy.write_text(policy_bytes)
    monkeypatch.setattr(main,'_ai_external_engine',lambda kind:True)
    monkeypatch.setattr(main,'_native_remote_infer',lambda *a:pytest.fail('Denied model reached remote transport'))
    with pytest.raises((LicenseDenied,json.JSONDecodeError)):
        main._split_lead_backing_vocals(tmp_path/'source.wav',tmp_path/'out',model_id='uvr_mdxnet_kara_2')
    assert not (tmp_path/'out').exists()
