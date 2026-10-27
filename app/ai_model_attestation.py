"""Opt-in trusted-worker Basic Pitch load receipts, not hardware attestation.

Authenticity comes from the existing assignment-scoped HTTPS worker credential.
Opaque executors and hostile operator/native libraries are not certified.
"""
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path

CONTEXT='MTA_AI_MODEL_CONTEXT'
RECEIPT='MTA_AI_MODEL_RECEIPT'
SCHEMA='mta-basic-pitch-load-1'


def _encode(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)


def _decode(raw):
    from .ai_remote_transport import _unique_pairs
    return json.loads(raw,object_pairs_hook=_unique_pairs)


def requirement(kind,decision):
    enabled=os.getenv('MTA_PULL_MODEL_ATTESTATION','off')
    if enabled=='off':return None
    if enabled!='basic-pitch-v1' or kind!='audio-to-midi-basic-pitch':
        raise ValueError('Model attestation pilot requires the explicit Basic Pitch adapter')
    from .ai_studio_adapter import MODEL_SHA256
    return {'schema':SCHEMA,'kind':kind,'policy':asdict(decision),'model_sha256':MODEL_SHA256,
            'adapter_sha256':hashlib.sha256(Path(__file__).with_name('ai_studio_adapter.py').read_bytes()).hexdigest()}


def context(task):
    return {key:task[key] for key in ('job_id','kind','instance','nonce','source_sha256')}|{'policy':task['policy']}


def record_loaded(model_bytes):
    """Called only after the supported ONNX session constructor succeeds."""
    raw=os.getenv(CONTEXT,'');path=os.getenv(RECEIPT,'')
    if not raw and not path:return
    if not raw or not path or len(raw)>8192:raise ValueError('Invalid model receipt context')
    value=_decode(raw)
    if not isinstance(value,dict) or value.get('kind')!='audio-to-midi-basic-pitch':
        raise ValueError('Unsupported model receipt context')
    value={'schema':SCHEMA,'context':value,'pid':os.getpid(),
           'model_sha256':hashlib.sha256(model_bytes).hexdigest()}
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0)
    with os.fdopen(os.open(path,flags,0o600),'w') as stream:
        stream.write(_encode(value));stream.flush();os.fsync(stream.fileno())


def validate(receipt,expected,task,*,pid=None):
    if (not isinstance(receipt,dict) or set(receipt)!={'schema','context','pid','model_sha256'}
            or receipt['schema']!=SCHEMA or receipt['context']!=context(task)
            or receipt['model_sha256']!=expected['model_sha256']
            or type(receipt['pid']) is not int or receipt['pid']<=0
            or (pid is not None and receipt['pid']!=pid)):
        raise ValueError('Original loaded-model receipt required')
    # Canonical JSON also prevents bool/int equivalence inside the context.
    if _encode(receipt['context'])!=_encode(context(task)):
        raise ValueError('Original model receipt context changed')
    return receipt
