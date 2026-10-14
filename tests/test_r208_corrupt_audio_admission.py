"""Malformed durable audio payloads cannot execute or bypass settlement."""
import pytest
import time
from app import ai_arranger_runtime as queue

@pytest.mark.parametrize('payload', ['{malformed', '[]', '{"schema_version":2}', 'null'])
def test_corrupt_durable_audio_payload_fails_closed(tmp_path, monkeypatch, payload):
    monkeypatch.setattr(queue, '_ROOT', tmp_path)
    jid = 'bad-audio-' + str(abs(hash(payload)))
    ran = []
    with queue._db() as con:
        con.execute('INSERT INTO jobs(job_id,project_id,operation,state,rank,created_at,phase,message,payload_json) VALUES(?,?,?,?,?,?,?,?,?)',
                    (jid,'project','arranger','queued',1,0,'queued','',payload))
    assert queue.durable_audio_job(jid)
    queue._spawn(jid, lambda progress: ran.append(True))
    for _ in range(150):
        if queue.get(jid)['state'] == 'blocked':
            break
        time.sleep(.02)
    assert queue.get(jid)['state'] == 'blocked'
    assert not ran

def test_in_memory_audio_preserves_legacy_behavior(tmp_path, monkeypatch):
    monkeypatch.setattr(queue, '_ROOT', tmp_path)
    with queue._db() as con:
        con.execute('INSERT INTO jobs(job_id,project_id,operation,state,rank,created_at,phase,message,payload_json) VALUES(?,?,?,?,?,?,?,?,?)',
                    ('legacy-audio','project','arranger','queued',1,0,'queued','',None))
    assert not queue.durable_audio_job('legacy-audio')
