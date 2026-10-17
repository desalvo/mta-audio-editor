"""Persistent diagnostic-only counters; never inputs to ledger settlement."""
import json
import math
from .auth import db


def store(job_id,payload):
    clean={key:float(payload[key]) for key in ('cpu_seconds_estimated','gpu_seconds_estimated')
      if type(payload.get(key)) in (int,float) and math.isfinite(payload[key]) and 0<=payload[key]<1e18}
    if not clean:return
    with db() as con:
        con.execute('''CREATE TABLE IF NOT EXISTS ai_compute_job_diagnostics
          (job_id TEXT PRIMARY KEY, payload TEXT NOT NULL)''')
        con.execute('INSERT INTO ai_compute_job_diagnostics VALUES(?,?) ON CONFLICT(job_id) DO UPDATE SET payload=excluded.payload',
          (job_id,json.dumps(clean,allow_nan=False)))


def read(con,user_id):
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name='ai_compute_job_diagnostics'").fetchone():return {}
    return {r[0]:json.loads(r[1]) for r in con.execute('''SELECT d.job_id,d.payload FROM ai_compute_job_diagnostics d
      JOIN ai_compute_jobs j ON j.id=d.job_id WHERE j.user_id=?''',(user_id,))}
