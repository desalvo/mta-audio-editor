"""Original admitted policy propagation to supported trusted subprocess adapters.

The environment is a parent/child consistency boundary, not remote attestation
or confinement of an operator-owned opaque executable.
"""
from dataclasses import asdict
import json
import os

KEY='MTA_AI_ADMITTED_POLICY'


def admitted_env(kind,decision):
    return {KEY:json.dumps({'schema':'mta-execution-policy-1','kind':kind,'decision':asdict(decision)},
                          sort_keys=True,separators=(',',':'),allow_nan=False)}


def verify_plan(plan):
    from .ai_remote_transport import _unique_pairs
    from .model_license_policy import evaluate
    raw=os.environ.get(KEY,'')
    if not raw or len(raw)>8192:
        raise ValueError('Original admitted worker policy required')
    value=json.loads(raw,object_pairs_hook=_unique_pairs)
    if (not isinstance(value,dict) or set(value)!={'schema','kind','decision'}
            or value['schema']!='mta-execution-policy-1' or not isinstance(plan,dict)
            or value['kind']!=plan.get('kind')):
        raise ValueError('Original admitted worker kind required')
    actual=admitted_env(value['kind'],evaluate(value['kind'],plan))[KEY]
    if json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)!=actual:
        raise ValueError('Worker policy or installed assets changed since admission')
