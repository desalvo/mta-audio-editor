from app import ai_arranger_runtime as queue
from app import ai_publish_outbox as publish

def test_interrupted_job_reconciles_after_durable_publication(tmp_path, monkeypatch):
    monkeypatch.setattr(queue, '_ROOT', tmp_path)
    with queue._db() as db:
        db.execute("INSERT INTO jobs(job_id,project_id,operation,state,rank,created_at,phase,message) VALUES('pub1','p','arranger','interrupted',1,1,'interrupted','crash')")
        db.execute("INSERT INTO terminal_receipts(job_id,state,committed_at) VALUES('pub1','interrupted',1)")
    publish.stage('pub1', 'p', b'audio', {'mode':'arranger'})
    assert publish.recover(lambda *a: None) == 1
    assert queue.reconcile_published_audio('pub1')
    assert queue.get('pub1')['state'] == 'completed'
    assert queue.terminal_receipt('pub1')['state'] == 'completed'
    assert queue.reconcile_published_audio('pub1')
