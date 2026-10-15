"""The disposable APT fixture must not weaken production RPM requirements."""
import pytest

from scripts.repositories.preflight_package_copy import prepare


def test_apt_only_requires_disposable_ci(tmp_path, monkeypatch):
    source = tmp_path / 'incoming'
    source.mkdir()
    (source / 'fixture.deb').write_bytes(b'fixture')
    for name in ('CI', 'MTA_CI_DISPOSABLE_CONTAINER', 'MTA_CI_APT_ONLY'):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValueError, match='disposable CI'):
        prepare(source, tmp_path / 'out', 'early', apt_only=True)
    monkeypatch.setenv('CI', 'true')
    monkeypatch.setenv('MTA_CI_DISPOSABLE_CONTAINER', '1')
    monkeypatch.setenv('MTA_CI_APT_ONLY', '1')
    prepare(source, tmp_path / 'out', 'early', apt_only=True)
    with pytest.raises(ValueError, match='rpm/el9'):
        prepare(source, tmp_path / 'out', 'early')
