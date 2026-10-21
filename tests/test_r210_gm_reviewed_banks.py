import hashlib
import pytest
from app import gm_banks
from app.gm_instruments import validate


def sources(tmp_path):
    sf=tmp_path/'source.sf2';sf.write_bytes(b'RIFF'+(40).to_bytes(4,'little')+b'sfbk'+b'fixture'*4)
    license=tmp_path/'COPYING';license.write_text('Synthetic test notice, not a real SoundFont license')
    return sf,license,hashlib.sha256(sf.read_bytes()).hexdigest()


def install(tmp_path,monkeypatch,**overrides):
    from app import gm_installer
    folder=tmp_path/'managed';folder.mkdir(exist_ok=True)
    monkeypatch.setattr(gm_installer,'root',lambda:folder)
    source,license,sha=sources(tmp_path)
    kwargs=dict(name='Fixture',sha256=sha,license_id='MIT',license_file=license,
                evidence_url='https://example.com/license',rights_reviewed=True)
    kwargs.update(overrides)
    return gm_banks.install(source,'sf2-example',**kwargs)


def test_install_hash_persist_and_reject_tampered_bank(tmp_path,monkeypatch):
    value=install(tmp_path,monkeypatch)
    path=gm_banks.bank_path(value['id'])
    assert path.read_bytes()==sources(tmp_path)[0].read_bytes()
    assert gm_banks.catalog()[0]['available']
    assert validate({'bank_id':'sf2-example'})['bank_id']=='sf2-example'
    with pytest.raises(ValueError,match='already installed'):install(tmp_path,monkeypatch)
    path.write_bytes(path.read_bytes()+b'altered')
    with pytest.raises(ValueError,match='checksum'):gm_banks.bank_path(value['id'])
    assert not gm_banks.catalog()[0]['available']


@pytest.mark.parametrize('overrides',[{'rights_reviewed':False},{'license_id':'Unreviewed'},{'sha256':'0'*64},
                                      {'evidence_url':'http://example.com/license'}])
def test_invalid_install_never_activates(tmp_path,monkeypatch,overrides):
    with pytest.raises(ValueError):install(tmp_path,monkeypatch,**overrides)
    assert gm_banks.catalog()==[]


def test_license_notice_integrity(tmp_path,monkeypatch):
    value=install(tmp_path,monkeypatch)
    path=gm_banks.bank_path(value['id'])
    path.with_name('LICENSE.txt').write_text('replaced')
    with pytest.raises(ValueError,match='license notice checksum'):gm_banks.bank_path(value['id'])
