"""Operational history never deletes metering; notifications outlive the modal."""
import json
import os
import time

from fastapi.testclient import TestClient
import pytest
from app import ai_arranger_runtime as queue, ai_job_views as views


@pytest.fixture
def jobs(tmp_path, monkeypatch):
    monkeypatch.setattr(queue, '_ROOT', tmp_path)
    def add(jid, state='completed', project='mine', created=1):
        with queue._db() as con:
            con.execute('''INSERT INTO jobs(job_id,project_id,operation,state,rank,created_at,
                started_at,completed_at,phase,message,runner_pid,runner_identity,payload_json)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (jid, project, 'arranger', state, created, created, created,
                 time.time() if state in views.TERMINAL else None, state, 'safe',
                 os.getpid() if state == 'running' else None,
                 queue._process_identity(os.getpid()) if state == 'running' else None,
                 '{"secret":"DO_NOT_EXPOSE"}'))
            if state in views.TERMINAL:
                con.execute('INSERT INTO terminal_receipts VALUES(?,?,?)', (jid, state, time.time()))
    return add


def test_history_selections_preserve_receipts_and_other_actors(jobs):
    for i in range(5): jobs('job'+str(i), created=i+1)
    jobs('foreign', project='other', created=10)
    jobs('active', 'queued', created=11)
    allow=lambda pid: pid=='mine'
    assert views.bulk(7, allow, {'action':'archive','mode':'count','count':2,'preview':True})['ids']==['job4','job3']
    assert views.bulk(7, allow, {'action':'archive','mode':'range','start':2,'end':4})['changed']==2
    assert views.bulk(7, allow, {'action':'archive','mode':'selected','ids':['foreign','active','job0']})['changed']==1
    assert views.bulk(7, allow, {'action':'archive','mode':'all'})['changed']==2
    feed=views.feed(7,allow)
    assert [j['job_id'] for j in feed['jobs']]==['active']
    assert len(views.feed(8,allow)['jobs'])==6
    assert 'DO_NOT_EXPOSE' not in json.dumps(feed)
    with queue._db() as con:
        assert con.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]==7
        assert con.execute('SELECT COUNT(*) FROM terminal_receipts').fetchone()[0]==6


def test_notification_inbox_independent_of_filters_and_ack_survives_reload(jobs,monkeypatch):
    clock=[100.]
    monkeypatch.setattr(views.time,'time',lambda:clock[0])
    jobs('old')
    jobs('working','running',created=2)
    clock[0]=101.
    assert views.feed(7,lambda _:True)['notifications']==[]
    clock[0]=102.
    with queue._db() as con:
        con.execute("UPDATE jobs SET state='completed',completed_at=? WHERE job_id='working'",(time.time(),))
    for _ in range(2):
        data=views.feed(7,lambda _:True,{'state':'active'})
        assert data['jobs']==[]
        assert [j['job_id'] for j in data['notifications']]==['working']
    views.acknowledge(7,lambda _:True,['working'])
    assert views.feed(7,lambda _:True)['notifications']==[]
    # A different user has no historical flood on first visit.
    clock[0]=103.
    assert views.feed(8,lambda _:True)['notifications']==[]


def test_cancel_selection_skips_terminal_and_exclusions_prevent_repeat_batches(jobs):
    jobs('done');jobs('waiting','queued',created=2);jobs('blocked','blocked',created=3)
    body={'action':'cancel','mode':'all','exclude_ids':['blocked']}
    assert views.bulk(7,lambda _:True,{**body,'preview':True})['ids']==['waiting']
    assert views.bulk(7,lambda _:True,body)['changed']==1
    assert queue.get('waiting')['state']=='cancelled'
    assert queue.get('blocked')['state']=='blocked'
    assert queue.get('done')['state']=='completed'


@pytest.mark.parametrize('body',[
    {'mode':'range','start':10,'end':1},{'count':True},{'count':5001},
    {'ids':['../escape']},{'start':float('nan')},{'exclude_ids':'bad'},
    {'mode':'other'},{'state':'secret'},{'preview':'yes'},
])
def test_invalid_bulk_fail_closed(jobs,body):
    with pytest.raises(ValueError):views.bulk(7,lambda _:True,{'action':'archive',**body})


def test_job_api_auth_acl_csrf_and_admin_redirect(jobs,monkeypatch):
    from app import main,auth
    from app.models import Project
    identity=[None]
    monkeypatch.setattr(main,'session_user',lambda _:identity[0])
    monkeypatch.setattr(auth,'session_user',lambda _:identity[0])
    monkeypatch.setattr(main,'check_basic_auth',lambda _:False)
    monkeypatch.setattr(main,'public_user',lambda u:u)
    monkeypatch.setattr(main,'load_project',lambda pid:Project(id=pid,title='Test',owner_user_id=7 if pid=='mine' else 8))
    jobs('owned');jobs('foreign',project='other');headers={'x-mta-request':'1'}
    client=TestClient(main.app)
    assert client.get('/api/ai-execution/jobs').status_code==401
    assert client.post('/api/ai-execution/jobs/bulk',json={'action':'archive'},headers=headers).status_code==401
    identity[0]={'id':7,'role':'user'}
    assert [j['job_id'] for j in client.get('/api/ai-execution/jobs').json()['jobs']]==['owned']
    assert client.post('/api/ai-execution/jobs/bulk',json={'action':'archive'}).status_code==403
    assert client.post('/api/ai-execution/jobs/bulk',json={'action':'archive','mode':'selected','ids':['foreign']},headers=headers).json()['changed']==0
    assert client.get('/admin',follow_redirects=False).status_code==403
    identity[0]={'id':9,'role':'admin'}
    redirect=client.get('/admin',follow_redirects=False)
    assert redirect.status_code==303 and redirect.headers['location']=='/settings'
    assert len(client.get('/api/ai-execution/jobs').json()['jobs'])==2


def test_feed_live_progress_public_allowlist_and_queue_positions(jobs,tmp_path):
    jobs('live','running');jobs('waiting','queued',created=2)
    (tmp_path/'live.progress.json').write_text(json.dumps({'progress_percent':60,'progress_source':'ace-dit-evaluations',
        'steps_completed':2,'steps_total':8,'gpu_seconds_estimated':4,'gpu_metrics_source':'ace-torch-profiler',
        'gpu_metrics_status':'profiling','payload_json':'secret'}))
    data=views.feed(7,lambda _:True)
    live=next(j for j in data['jobs'] if j['job_id']=='live')
    assert live['gpu_seconds'] is None and live['gpu_seconds_estimated']==4
    assert live['steps_completed']==2 and live['progress_estimated'] is True
    waiting=next(j for j in data['jobs'] if j['job_id']=='waiting')
    assert waiting['queue_position']==1 and waiting['jobs_ahead']==0
    assert 'payload_json' not in live and 'runner_pid' not in live


def test_history_pagination_does_not_change_global_running_badge(jobs):
    jobs('running','running',created=1)
    for n in range(5): jobs('done'+str(n),created=n+2)
    first=views.feed(7,lambda _:True,limit=2)
    assert first['active_count']==1 and first['has_more'] is True
    second=views.feed(7,lambda _:True,limit=2,offset=2)
    assert not set(j['job_id'] for j in first['jobs']) & set(j['job_id'] for j in second['jobs'])
    filtered=views.feed(7,lambda _:True,{'state':'terminal'},limit=2,offset=4)
    assert filtered['active_count']==1 and filtered['has_more'] is False
    with pytest.raises(ValueError):views.feed(7,lambda _:True,offset=-1)
