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
    assert rows[1]['action'] == 'manual-review'


def test_existing_mount_idempotent():
    rows = plan({'200': 'tags: mta-audio-editor;mta-gpu-agent\nmp0: /run/mta-gpu-agent,mp=/run/mta-gpu-agent,ro=1\n'})
    assert rows[0]['action'] == 'none'
