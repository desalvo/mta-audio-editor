"""Reject arbitrary banks, unsafe receipts, cancellation and corrupt archives."""
from pathlib import Path
import pytest
from app import auth


@pytest.fixture
def assets(tmp_path,monkeypatch):
    monkeypatch.setattr(auth,'DATA_ROOT',tmp_path)
    return tmp_path


def test_unknown_bank_cannot_reach_native_parser(assets):
    from app.vocal_banks import bank
    with pytest.raises(ValueError,match='Unknown'):bank('../../untrusted')
    with pytest.raises(ValueError,match='not installed'):bank('air')


def test_cancelled_bank_install_leaves_no_assets(assets):
    from app.vocal_banks import install,root
    with pytest.raises(RuntimeError,match='cancelled'):install('air',lambda:True,lambda *args:None)
    assert list(root().iterdir())==[]


def test_bank_symlink_is_never_followed(assets):
    from app.vocal_banks import bank,root
    outside=assets/'untrusted.voice';outside.write_bytes(b'untrusted')
    link=root()/'air.voice'
    try:link.symlink_to(outside)
    except OSError:pytest.skip('Symlinks unavailable on this platform')
    with pytest.raises(ValueError,match='Unsafe'):bank('air')
    assert outside.read_bytes()==b'untrusted'


def test_corrupt_offline_gm_archive_is_not_activated(assets):
    from app.gm_installer import install,root
    corrupt=assets/'corrupt.tar.gz';corrupt.write_bytes(b'not the reviewed archive')
    with pytest.raises(ValueError,match='checksum'):install(lambda:False,lambda *args:None,archive=corrupt)
    assert list(root().iterdir())==[]


def test_cancelled_gm_download_is_not_activated(assets,monkeypatch):
    from app.gm_installer import install,root
    from app import secure_https
    import io
    monkeypatch.setattr(secure_https,'https_urlopen',lambda *args,**kwargs:io.BytesIO(b'partial'))
    with pytest.raises(RuntimeError,match='cancelled'):install(lambda:True,lambda *args:None)
    assert list(root().iterdir())==[]


def test_license_policy_symlink_is_not_accepted(assets):
    from app.model_license_policy import overrides,LicenseDenied,_path
    target=assets/'outside.json';target.write_text('{}')
    try:Path(_path()).symlink_to(target)
    except OSError:pytest.skip('Symlinks unavailable on this platform')
    with pytest.raises(LicenseDenied,match='Unsafe'):overrides()
    assert target.read_text()=='{}'
