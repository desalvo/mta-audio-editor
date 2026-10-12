from scripts import mta_proxmox_gpu_readiness as module

def test_readiness_without_local_pve(tmp_path, monkeypatch):
    monkeypatch.setattr(module, 'CONF', tmp_path / 'missing')
    monkeypatch.setattr(module, 'command', lambda *a, **kw: {'ok': True, 'output': 'active', 'error': ''})
    report = module.audit()
    assert report['containers'] == []
    assert 'warning' in report

def test_readiness_detects_tagged_mounted_ct(tmp_path, monkeypatch):
    (tmp_path / '130.conf').write_text('tags: mta-audio-editor;mta-gpu-agent\n'
     'mp0: /run/mta-gpu-agent,mp=/run/mta-gpu-agent,ro=1,replicate=0,shared=1\n')
    (tmp_path / '131.conf').write_text('tags: backup\n')
    monkeypatch.setattr(module, 'CONF', tmp_path)
    def fake_command(args, **kwargs):
        if args[:2] == ['pvesr', 'list']:
            return {'ok': True, 'output': 'JobID Target\n130-2 local/other\n', 'error': ''}
        if args[:2] == ['pct', 'status']:
            return {'ok': True, 'output': 'status: running', 'error': ''}
        return {'ok': True, 'output': 'active', 'error': ''}
    monkeypatch.setattr(module, 'command', fake_command)
    rows = module.audit()['containers']
    assert len(rows) == 1
    assert rows[0]['mount_replication_safe_flags']
    assert rows[0]['replication_jobs'] == ['130-2']

def test_readiness_flags_mount_missing_flags(tmp_path, monkeypatch):
    (tmp_path / '132.conf').write_text('tags: mta-audio-editor;mta-gpu-agent\n'
       'mp1: /run/mta-gpu-agent,mp=/run/mta-gpu-agent,ro=1\n')
    monkeypatch.setattr(module, 'CONF', tmp_path)
    monkeypatch.setattr(module, 'command', lambda *a, **kw: {'ok': True, 'output': '', 'error': ''})
    row = module.audit()['containers'][0]
    assert row['mount_requires_review'] and not row['mount_replication_safe_flags']
