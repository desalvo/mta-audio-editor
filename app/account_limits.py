"""Personal storage and accounting summary; never infer payments or GPU usage."""
import math
import os
from pathlib import Path
import stat
import time
from . import auth, ai_billing, ai_usage_reporting


def project_storage(user_id, projects, project_path):
    seen=set();used=audio=0;owned=[p for p in projects if p.owner_user_id==user_id]
    def walk_error(error):
        if not isinstance(error,FileNotFoundError):raise error
    for project in owned:
        root=Path(project_path(project.id))
        if root.is_symlink():continue
        for directory,dirs,files in os.walk(root,followlinks=False,onerror=walk_error):
            dirs[:]=[name for name in dirs if not (Path(directory)/name).is_symlink()]
            for name in files:
                path=Path(directory)/name
                try:info=path.stat(follow_symlinks=False)
                except FileNotFoundError:continue
                key=(info.st_dev,info.st_ino)
                if not stat.S_ISREG(info.st_mode) or key in seen:continue
                seen.add(key);used+=info.st_size
                if 'audio' in path.relative_to(root).parts:audio+=info.st_size
    return {'used_bytes':used,'audio_bytes':audio,'other_bytes':used-audio,
      'project_count':len(owned),'track_count':sum(len(p.tracks) for p in owned),
      'measurement':'owned-project-files-unique-inodes'}


def summary(user_id, storage, *, at=None):
    now=time.time() if at is None else at
    user=auth.get_user(user_id)
    if not user:raise ValueError('User not found')
    quota=int(user['workspace_quota_bytes'] or 0)
    rows=ai_usage_reporting.records(user_id,0,max(1,now+1))
    report={**ai_usage_reporting.aggregate(rows),'billing_enabled':ai_billing.user_billing_enabled(user_id)}
    with auth.db() as con:
        ai_billing._init(con)
        periods=[dict(r) for r in con.execute('SELECT start_ts,end_ts,total_micro FROM ai_billing_periods WHERE user_id=?',(user_id,))]
    pending=[];closed=[]
    for row in rows:
        if row['origin']!='ledger' or row.get('billable')!=1 or row['status']!='done' or row['resource_source']=='unmetered':continue
        destination=closed if any(p['start_ts']<=row['started_at']<p['end_ts'] for p in periods) else pending
        destination.append(row)
    def total(items,key):return sum(float(r['usage'].get(key,0)) for r in items)
    resources={}
    for name in ('cpu','gpu'):
        key=name+'_seconds';known=key in report['usage'];verified=report['usage'].get(key)
        resources[name]={'verified_seconds':verified if known else None,
          'diagnostic_seconds':report['diagnostic'].get(key+'_estimated'),
          'closed_seconds':total(closed,key),'pending_seconds':total(pending,key),
          'other_verified_seconds':max(0,(verified or 0)-total(closed,key)-total(pending,key))}
        for value in resources[name].values():
            if value is not None and (not math.isfinite(value) or value<0):raise ValueError('Invalid resource summary')
    return {'user_id':user_id,'as_of':now,'storage':{**storage,'quota_bytes':quota or None,'unlimited':not quota,
      'remaining_bytes':max(0,quota-storage['used_bytes']) if quota else None,
      'percent':storage['used_bytes']/quota*100 if quota else None},
      'resources':resources,'jobs':report['jobs'],'unmetered_jobs':report['unmetered_jobs'],
      'billing':{'enabled':report['billing_enabled'],'currency':'EUR',
        'pending_estimate_micro':sum(r['amount_micro'] for r in pending),
        'closed_total_micro':sum(p['total_micro'] for p in periods),'closed_periods':len(periods),
        'outstanding_micro':None,'payment_status':'not-tracked','estimate_is_invoice':False}}
