from scripts.check_gm_soundfont import audit

def test_audit_fails_closed_without_runtime(monkeypatch):
    monkeypatch.setattr('scripts.check_gm_soundfont.status',lambda:{'available':False,'error':'assets missing'})
    result=audit()
    assert result['certified'] is False
    assert result['programs']==[]
    assert 'blocked' in result
