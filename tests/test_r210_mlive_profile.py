"""Profile isolation, legacy migration and export snapshots."""
import json

import pytest
from fastapi import HTTPException, Response

from app import auth, main, mlive_profile
from app.models import DEFAULT_MERISH_SYL_KEY, DEFAULT_MERISH_USER_ID, MtaExportRequest, Project, ProjectExportRequest


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, 'DATA_ROOT', tmp_path)
    return tmp_path


def test_profiles_are_independent_and_validate_values(isolated):
    first = mlive_profile.get(1)
    assert first == {'merish_user_id': DEFAULT_MERISH_USER_ID, 'merish_syl_key': DEFAULT_MERISH_SYL_KEY}
    custom = bytes(range(256)).hex()
    mlive_profile.save(1, '123456', custom)
    assert mlive_profile.get(1)['merish_syl_key'] == custom
    assert mlive_profile.get(2) == first
    with pytest.raises(ValueError):
        mlive_profile.save(2, '123456', '00' * 256)
    assert mlive_profile.get(2) == first


def test_legacy_project_identity_is_not_serialized_and_does_not_override_profile(isolated):
    custom = bytes(range(256)).hex()
    legacy = Project.model_validate({'id':'p', 'title':'Legacy', 'merish_user_id':'123456', 'merish_syl_key':custom})
    assert 'merish_user_id' not in legacy.model_dump() and 'merish_syl_key' not in json.loads(legacy.model_dump_json())
    mlive_profile.adopt_legacy(1, legacy)
    assert mlive_profile.get(1) == {'merish_user_id':'123456', 'merish_syl_key':custom}
    mlive_profile.save(1, '654321', DEFAULT_MERISH_SYL_KEY)
    mlive_profile.adopt_legacy(1, legacy)
    assert mlive_profile.get(1)['merish_user_id'] == '654321'
    assert mlive_profile.get(2)['merish_user_id'] == DEFAULT_MERISH_USER_ID


def test_saved_project_does_not_contain_user_profile(isolated, monkeypatch):
    from app import storage
    monkeypatch.setattr(storage, 'ROOT', isolated / 'projects')
    project = storage.create_project('Portable')
    project.merish_user_id = '123456'
    project.merish_syl_key = bytes(range(256)).hex()
    storage.save_project(project)
    data = json.loads((storage.pdir(project.id) / 'project.json').read_text())
    assert 'merish_user_id' not in data and 'merish_syl_key' not in data


def test_legacy_portable_archive_omits_user_profile_without_changing_source(isolated, monkeypatch):
    import zipfile
    from app import storage
    monkeypatch.setattr(storage, 'ROOT', isolated / 'projects')
    project = storage.create_project('Legacy portable')
    source = storage.pdir(project.id) / 'project.json'
    data = json.loads(source.read_text())
    data.update(merish_user_id='123456', merish_syl_key=bytes(range(256)).hex(), project_kind_version=1)
    source.write_text(json.dumps(data))
    archive = storage.write_project_archive(project.id, isolated / 'project.maeprojz')
    with zipfile.ZipFile(archive) as zipped:
        exported = json.loads(zipped.read('project/project.json'))
    assert 'merish_user_id' not in exported and 'merish_syl_key' not in exported
    assert json.loads(source.read_text())['merish_user_id'] == '123456'


def test_export_view_uses_executing_user_without_mutating_project(isolated):
    legacy = Project(id='p', title='Legacy', merish_user_id='123456', merish_syl_key=bytes(range(256)).hex())
    mlive_profile.save(1, '654321', DEFAULT_MERISH_SYL_KEY)
    one = mlive_profile.apply(legacy, mlive_profile.get(1))
    two = mlive_profile.apply(legacy, mlive_profile.get(2))
    assert one.merish_user_id == '654321' and two.merish_user_id == DEFAULT_MERISH_USER_ID
    assert legacy.merish_user_id == '123456'
    assert 'merish_syl_key' not in one.model_dump()


def test_background_export_captures_executing_user_profile(isolated, monkeypatch):
    custom = bytes(range(256)).hex()
    mlive_profile.save(7, '123456', custom)
    project = Project(id='p', title='Shared', owner_user_id=8)
    monkeypatch.setattr(main, '_project_for_actor', lambda request, pid: project)
    monkeypatch.setattr(main, '_actor', lambda request: {'id':7})
    captured = {}
    class Thread:
        def __init__(self, **kwargs): captured.update(kwargs)
        def start(self): pass
    monkeypatch.setattr(main, 'worker_thread', Thread)
    result = main.start_configured_project_export_job('p', ProjectExportRequest(format='mta', filename='out'), None)
    assert captured['args'][3] == {'merish_user_id':'123456', 'merish_syl_key':custom}
    assert custom not in json.dumps(result)
    mlive_profile.save(7, '654321', DEFAULT_MERISH_SYL_KEY)
    assert captured['args'][3]['merish_user_id'] == '123456'


def test_profile_api_binds_to_authenticated_user(isolated, monkeypatch):
    actor = {'id': 11}
    monkeypatch.setattr(main, 'require_user', lambda request: actor)
    custom = bytes(range(256)).hex()
    response = Response()
    assert main.get_mlive_profile(None, response)['merish_user_id'] == DEFAULT_MERISH_USER_ID
    assert response.headers['Cache-Control'] == 'no-store'
    assert main.put_mlive_profile(None, {'merish_user_id':'123456', 'merish_syl_key':custom}, Response())['merish_user_id'] == '123456'
    actor['id'] = 12
    assert main.get_mlive_profile(None, Response())['merish_user_id'] == DEFAULT_MERISH_USER_ID
    with pytest.raises(HTTPException) as exc:
        main.put_mlive_profile(None, {'merish_user_id':'123456', 'merish_syl_key':custom, 'user_id':11}, Response())
    assert exc.value.status_code == 422
    assert mlive_profile.get(11)['merish_user_id'] == '123456'


def test_shared_project_does_not_adopt_owner_legacy_settings(isolated, monkeypatch):
    legacy = Project(id='p', title='Shared', owner_user_id=8, merish_user_id='123456', merish_syl_key=bytes(range(256)).hex())
    monkeypatch.setattr(main, 'load_project', lambda pid: legacy)
    monkeypatch.setattr(main, '_actor', lambda request: {'id':7, 'role':'user'})
    monkeypatch.setattr(main, 'project_access', lambda *args, **kwargs: True)
    main._project_for_actor(None, 'p')
    assert mlive_profile.get(7)['merish_user_id'] == DEFAULT_MERISH_USER_ID


def test_owner_project_adopts_complete_legacy_identity_once(isolated, monkeypatch):
    legacy = Project(id='p', title='Old', owner_user_id=7, merish_user_id='123456', merish_syl_key=bytes(range(256)).hex())
    monkeypatch.setattr(main, 'load_project', lambda pid: legacy)
    monkeypatch.setattr(main, '_actor', lambda request: {'id':7, 'role':'user'})
    monkeypatch.setattr(main, 'project_access', lambda *args, **kwargs: True)
    main._project_for_actor(None, 'p')
    assert mlive_profile.get(7)['merish_user_id'] == '123456'
    mlive_profile.save(7, '654321', DEFAULT_MERISH_SYL_KEY)
    main._project_for_actor(None, 'p')
    assert mlive_profile.get(7)['merish_user_id'] == '654321'


def test_mapping_export_uses_requester_profile(isolated, monkeypatch):
    project = Project(id='p', title='Shared', owner_user_id=8)
    custom = bytes(range(256)).hex()
    mlive_profile.save(7, '123456', custom)
    monkeypatch.setattr(main, '_project_for_actor', lambda request, pid: project)
    monkeypatch.setattr(main, '_actor', lambda request: {'id':7})
    monkeypatch.setattr(main, 'validate_project_files', lambda project: None)
    monkeypatch.setattr(main, '_musical_export_project', lambda project: project.model_copy(deep=True))
    monkeypatch.setattr(main, 'validate_slot_mapping', lambda project, slots: slots)
    monkeypatch.setattr(main, 'pdir', lambda pid: isolated)
    captured = []
    monkeypatch.setattr(main, 'export_mta', lambda project, *args: captured.append(project))
    main.export_mta_with_mapping('p', MtaExportRequest(slots=[]), None)
    assert captured[0].merish_user_id == '123456' and captured[0].merish_syl_key == custom
    assert project.merish_user_id == DEFAULT_MERISH_USER_ID
