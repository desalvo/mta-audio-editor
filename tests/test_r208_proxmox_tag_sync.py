from scripts.mta_proxmox_tag_sync import eligible, plan


def test_two_tags_required():
    assert eligible('tags: backup;mta-audio-editor;mta-gpu-agent\n')
    assert not eligible('tags: mta-audio-editor\n')
    assert not eligible('tags: mta-gpu-agent\n')
    assert not eligible('tags: mta-audio-editor-fake;mta-gpu-agent\n')


def test_safe_planning():
    rows = plan({'101': 'tags: mta-audio-editor;mta-gpu-agent\nmp0: /data,mp=/data\n',
                 '102': 'tags: mta-audio-editor;mta-gpu-agent\nunprivileged: 1\n',
                 '103': 'tags: mta-audio-editor\n'})
    assert [x['ctid'] for x in rows] == [101, 102]
    assert rows[0]['action'] == 'add-mount'
    assert rows[0]['mount_id'] == 1
    assert rows[1]['action'] == 'add-mount'
    assert rows[1]['mapped_root_uid'] == 100000


def test_existing_mount_idempotent():
    rows = plan({'200': 'tags: mta-audio-editor;mta-gpu-agent\nmp0: /run/mta-gpu-agent,mp=/run/mta-gpu-agent,ro=1\n'})
    assert rows[0]['action'] == 'none'


def test_custom_idmap_is_manual_review():
    rows = plan({'130': 'tags: mta-audio-editor;mta-gpu-agent\nunprivileged: 1\nlxc.idmap: u 0 200000 65536\n'})
    assert rows[0]['action'] == 'manual-review'
    assert rows[0]['mapped_root_uid'] is None


def test_replication_nodes_not_hardcoded_and_running_guest_deferred(tmp_path, monkeypatch):
    from scripts import mta_proxmox_tag_sync as mod
    (tmp_path / '130.conf').write_text('tags: prod;mta-audio-editor;mta-gpu-agent\nunprivileged: 1\n')
    monkeypatch.setattr(mod, 'is_running', lambda ctid: True)
    monkeypatch.setattr(mod.shutil, 'which', lambda cmd: '/usr/bin/setfacl')
    monkeypatch.setattr(mod.pathlib.Path, 'is_socket', lambda self: True)
    calls = []
    monkeypatch.setattr(mod.subprocess, 'run', lambda argv, **kwargs: calls.append(argv))
    rows = mod.sync(tmp_path, apply=True)
    assert rows[0]['action'] == 'deferred-until-stopped'
    assert not any(argv[:2] == ['pct', 'set'] for argv in calls)
    assert 'gwads07' not in (tmp_path / '130.conf').read_text()


def test_stopped_guest_mount_excludes_replication(tmp_path, monkeypatch):
    from scripts import mta_proxmox_tag_sync as mod
    (tmp_path / '133.conf').write_text('tags: mta-audio-editor;mta-gpu-agent\n')
    monkeypatch.setattr(mod, 'is_running', lambda ctid: False)
    commands = []
    monkeypatch.setattr(mod.subprocess, 'run', lambda argv, **kwargs: commands.append(argv))
    rows = mod.sync(tmp_path, apply=True)
    assert rows[0]['action'] == 'configured-pending-restart'
    assert commands == [['pct', 'set', '133', '-mp0', '/run/mta-gpu-agent,mp=/run/mta-gpu-agent,ro=1,replicate=0']]
