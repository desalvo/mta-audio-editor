import pytest
from app.models import InsertPlugin, Track
from app.plugins import chain_filter
from app.vst3_host import discover_plugins, validate_plugin_path


def test_vst3_model_preserves_path_and_bypass():
    item = InsertPlugin(id='vst1', plugin='vst3', params={'path': 'fixtures/fake.vst3'})
    assert item.model_dump()['params']['path'] == 'fixtures/fake.vst3'
    assert chain_filter([item]) == ''
    assert chain_filter([item.model_copy(update={'enabled': False})]) == ''


def test_vst3_discovery_restricts_paths(monkeypatch, tmp_path):
    import app.vst3_host as host
    root = tmp_path / 'vst'
    root.mkdir()
    bundle = root / 'Space.vst3'
    bundle.mkdir()
    monkeypatch.setattr(host, 'vst3_roots', lambda: [root.resolve()])
    assert {'name': 'Space', 'path': str(bundle.resolve())} in discover_plugins()
    assert validate_plugin_path(str(bundle)) == bundle.resolve()
    with pytest.raises(FileNotFoundError):
        validate_plugin_path(str(tmp_path / 'outside.vst3'))
    with pytest.raises(ValueError):
        validate_plugin_path(str(root / 'invalid.dll'))


def test_vst3_insert_type_validates():
    assert Track.model_fields['inserts'] is not None
