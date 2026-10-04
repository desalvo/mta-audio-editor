import pytest
from fastapi import HTTPException


def test_model_storage_usage_and_delete_local(monkeypatch, tmp_path):
    import app.model_updater as m
    root=tmp_path/'models'; core=root/'coreml'; onnx=root/'onnx'; server=root/'server'
    for d in (core,onnx,server): d.mkdir(parents=True)
    (core/'demo.mlmodel').write_bytes(b'a'*10)
    (core/'demo.mlmodel.json').write_text('{"id":"demo"}')
    (onnx/'x.onnx').write_bytes(b'b'*20)
    monkeypatch.setattr(m,'ROOT',root); monkeypatch.setattr(m,'COREML_DIR',core); monkeypatch.setattr(m,'ONNX_DIR',onnx); monkeypatch.setattr(m,'SERVER_DIR',server)
    monkeypatch.setattr(m,'BLACKLIST_FILE',root/'blacklist.json')
    usage=m.model_storage_usage()
    assert usage['total_bytes'] >= 30 and usage['coreml_bytes'] >= 10 and usage['onnx_bytes'] == 20
    result=m.delete_local_model('demo')
    assert result['model_id']=='demo' and result['blacklisted'] is False
    assert not (core/'demo.mlmodel').exists()


def test_workspace_storage_payload_and_quota_guard(monkeypatch, tmp_path):
    import app.main as main
    import app.storage as storage
    monkeypatch.setattr(main,'STORAGE_ROOT',tmp_path)
    monkeypatch.setattr(storage,'ROOT',tmp_path)
    monkeypatch.setattr(main,'demucs_model_storage_usage',lambda:{'total_bytes':12,'coreml_bytes':1,'onnx_bytes':2,'server_bytes':9})
    p=storage.create_project('A','DAW',owner_user_id=7)
    (storage.pdir(p.id)/'audio'/'x.bin').write_bytes(b'x'*25)
    users=[{'id':7,'username':'u','display_name':'User','role':'user','workspace_quota_bytes':10000}]
    monkeypatch.setattr(main,'list_users',lambda:users)
    monkeypatch.setattr(main,'_actor',lambda request:{'id':7,'role':'user'})
    monkeypatch.setattr(main,'get_user',lambda uid:{'workspace_quota_bytes':10000})
    payload=main._storage_payload(object())
    assert len(payload['workspaces'])==1 and payload['workspaces'][0]['used_bytes'] >= 25
    assert payload['models']['total_bytes']==12
    main._ensure_workspace_capacity(7,1)
    with pytest.raises(HTTPException) as exc:
        main._ensure_workspace_capacity(7,100000)
    assert exc.value.status_code==413


def test_admin_quota_column_round_trip(tmp_path, monkeypatch):
    import app.auth as auth
    monkeypatch.setattr(auth,'DATA_ROOT',tmp_path)
    monkeypatch.setenv('MTA_ADMIN_USERNAME','admin')
    monkeypatch.setenv('MTA_ADMIN_PASSWORD','administrator-password')
    monkeypatch.setenv('MTA_ADMIN_EMAIL','admin@example.test')
    auth.init_auth_db()
    admin=auth.find_user('admin')
    user,token=auth.register_user('quotauser','quota@example.test','Quota','very-secure-password')
    assert auth.confirm_email(token)
    updated=auth.update_user_admin(user['id'],admin['id'],active=True,workspace_quota_bytes=123456)
    assert updated['workspace_quota_bytes']==123456
    with pytest.raises(ValueError):
        auth.update_user_admin(user['id'],admin['id'],workspace_quota_bytes=-1)
