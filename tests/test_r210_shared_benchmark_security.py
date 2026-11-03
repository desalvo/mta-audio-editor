"""Campaign restore rejects nonportable and executable archive entries before publication."""
from io import BytesIO
import json
import stat
import zipfile

import pytest
from app import auth,percussion_benchmark as bench


def archive(entries):
    stream=BytesIO()
    with zipfile.ZipFile(stream,'w') as target:
        for name,mode,data in entries:
            info=zipfile.ZipInfo(name);info.external_attr=mode<<16
            target.writestr(info,data)
    return stream.getvalue()


@pytest.mark.parametrize('name',[
    'CON.json','nul.wav','audio./candidate.wav','audio /candidate.wav',
    'audio/<candidate>.wav','audio/cafe\u0301.wav','audio/candidate\u202e.wav',
    'audio/candidate.svg','audio/candidate.py',
])
def test_campaign_import_refuses_nonportable_or_executable_names_before_publication(tmp_path,monkeypatch,name):
    monkeypatch.setattr(auth,'DATA_ROOT',tmp_path/'authority')
    with pytest.raises(ValueError,match='Unsafe'):
        bench.restore(archive([(name,stat.S_IFREG|0o600,b'not-authority')]), 1)
    assert not (tmp_path/'authority'/'ai-benchmarks'/'campaigns').exists()


@pytest.mark.parametrize('mode',[stat.S_IFLNK,stat.S_IFIFO,stat.S_IFCHR,stat.S_IFBLK,stat.S_IFSOCK,stat.S_IFDIR])
def test_campaign_import_refuses_special_archive_members_before_publication(tmp_path,monkeypatch,mode):
    monkeypatch.setattr(auth,'DATA_ROOT',tmp_path/'authority')
    with pytest.raises(ValueError,match='Unsafe'):
        bench.restore(archive([('audio/candidate.wav',mode|0o600,b'not-authority')]), 1)
    assert not (tmp_path/'authority'/'ai-benchmarks'/'campaigns').exists()


def test_campaign_import_refuses_case_aliases_before_publication(tmp_path,monkeypatch):
    monkeypatch.setattr(auth,'DATA_ROOT',tmp_path/'authority')
    entries=[(name,stat.S_IFREG|0o600,b'not-authority') for name in ('audio/Candidate.wav','audio/candidate.wav')]
    with pytest.raises(ValueError,match='Unsafe'):bench.restore(archive(entries), 1)
    assert not (tmp_path/'authority'/'ai-benchmarks'/'campaigns').exists()


def test_campaign_import_refuses_symlink_campaigns_parent(tmp_path,monkeypatch):
    monkeypatch.setattr(auth,'DATA_ROOT',tmp_path/'authority')
    outside=tmp_path/'outside';outside.mkdir()
    (bench.root()/'campaigns').symlink_to(outside,target_is_directory=True)
    config={'fixture':'data-only'}
    value={'schema':bench.SCHEMA,'id':'restored-safe','config':config,'config_sha256':bench.json_hash(config),'results':[]}
    with pytest.raises(ValueError,match='Unsafe campaign directory'):
        bench.restore(archive([('campaign.json',stat.S_IFREG|0o600,json.dumps(value).encode())]), 1)
    assert not list(outside.iterdir())
