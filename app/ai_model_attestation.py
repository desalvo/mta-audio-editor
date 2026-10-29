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
VERIFIED_SCHEMA='mta-reviewed-checkpoint-load-2'
VERIFIED_MODE='verified-pull-v1'
RIGHTS={
    'model_id':'basic-pitch','version':'0.4.0','license':'Apache-2.0',
    'upstream_commit':'9991303bba609a3b93089d13ec80d1d495083596',
    'source':'https://github.com/spotify/basic-pitch/tree/9991303bba609a3b93089d13ec80d1d495083596',
    'documents':{'LICENSE':'929c910bae2152fa87199a5d0660e09263419b7eee6d4b301d05ee2aaf211c37',
                 'NOTICE':'b810e55c0e3b520fabb45fc2ccc74880187bf84e309971968541cc812dcde905'},
    'runtime':{'basic-pitch':'0.4.0','onnxruntime':'1.23.2'},
}


def authorize(kind,plan):
    """Private pull contract; generic/opaque remote authorization is unchanged."""
    from .model_license_policy import authorize_remote_execution,evaluate,LicenseDenied
    if os.getenv('MTA_PULL_MODEL_ATTESTATION','off')!=VERIFIED_MODE:
        decision=authorize_remote_execution(kind,plan)
    else:
        if kind!='audio-to-midi-basic-pitch':
            raise LicenseDenied('No reviewed checkpoint load contract for this remote engine')
        decision=evaluate(kind,plan)
        if decision.model_id!='basic-pitch':raise LicenseDenied('Reviewed checkpoint identity mismatch')
    return decision,requirement(kind,decision)


def _encode(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)


def _decode(raw):
    from .ai_remote_transport import _unique_pairs
    return json.loads(raw,object_pairs_hook=_unique_pairs)


def requirement(kind,decision):
    enabled=os.getenv('MTA_PULL_MODEL_ATTESTATION','off')
    if enabled=='off':return None
    if enabled==VERIFIED_MODE:
        if kind!='audio-to-midi-basic-pitch' or decision.model_id!='basic-pitch':
            raise ValueError('No reviewed checkpoint load contract for this engine')
        from .ai_studio_adapter import MODEL_SHA256
        return {'schema':VERIFIED_SCHEMA,'kind':kind,'policy':asdict(decision),'model_sha256':MODEL_SHA256,
                'rights':RIGHTS,'rights_sha256':hashlib.sha256(_encode(RIGHTS).encode()).hexdigest(),
                'sources':{name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                           for name in ('ai_studio_adapter.py','ai_model_bytes.py','ai_model_attestation.py')}}
    if enabled!='basic-pitch-v1' or kind!='audio-to-midi-basic-pitch':
        raise ValueError('Model attestation pilot requires the explicit Basic Pitch adapter')
    from .ai_studio_adapter import MODEL_SHA256
    return {'schema':SCHEMA,'kind':kind,'policy':asdict(decision),'model_sha256':MODEL_SHA256,
            'adapter_sha256':hashlib.sha256(Path(__file__).with_name('ai_studio_adapter.py').read_bytes()).hexdigest()}


def context(task):
    value={key:task[key] for key in ('job_id','kind','instance','nonce','source_sha256')}|{'policy':task['policy']}
    required=task.get('model_requirement')
    if required and required.get('schema')==VERIFIED_SCHEMA:
        value|={'contract':required,'plan_sha256':hashlib.sha256(_encode(task['plan']).encode()).hexdigest()}
    return value


def verify_contract(required,decision):
    epoch=required.get('epoch')
    if (not isinstance(epoch,dict) or set(epoch)!={'regime','revision'} or
            epoch['regime'] not in ('COMMERCIAL','NON_COMMERCIAL') or
            type(epoch['revision']) is not int or epoch['revision']<0 or
            (epoch['regime']=='COMMERCIAL' and decision.mode!='cost_recovery')):
        raise ValueError('Original licensed execution epoch required')
    expected=requirement(required.get('kind'),decision)
    if expected is None or _encode({k:v for k,v in required.items() if k!='epoch'})!=_encode(expected):
        raise ValueError('Reviewed checkpoint rights or loader changed')


def runtime_identity():
    import importlib.metadata
    actual={name:importlib.metadata.version(name) for name in RIGHTS['runtime']}
    if actual!=RIGHTS['runtime']:raise ValueError('Unreviewed checkpoint runtime')
    distribution=importlib.metadata.distribution('basic-pitch')
    for name,digest in RIGHTS['documents'].items():
        matches=[p for p in distribution.files or [] if p.name==name and '.dist-info/' in str(p)]
        if len(matches)!=1:raise ValueError('Installed checkpoint rights evidence missing')
        path=Path(distribution.locate_file(matches[0]))
        if path.is_symlink() or path.stat().st_size>32768 or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise ValueError('Installed checkpoint rights evidence changed')
    return actual


def verify_before_load():
    value=_decode(os.environ.get(CONTEXT,'{}'))
    if isinstance(value,dict) and 'contract' in value:
        from .model_license_policy import Decision
        verify_contract(value['contract'],Decision(**value['policy']))
        runtime_identity()


def record_loaded(model_bytes):
    """Called only after the supported ONNX session constructor succeeds."""
    raw=os.getenv(CONTEXT,'');path=os.getenv(RECEIPT,'')
    if not raw and not path:return
    if not raw or not path or len(raw)>8192:raise ValueError('Invalid model receipt context')
    value=_decode(raw)
    if not isinstance(value,dict) or value.get('kind')!='audio-to-midi-basic-pitch':
        raise ValueError('Unsupported model receipt context')
    contract=value.get('contract')
    extra={}
    if contract is not None:
        from .model_license_policy import Decision
        verify_contract(contract,Decision(**value['policy']))
        extra={'rights_sha256':contract['rights_sha256'],'runtime':runtime_identity()}
        if hashlib.sha256(model_bytes).hexdigest()!=contract['model_sha256']:
            raise ValueError('Loaded checkpoint differs from the original reviewed contract')
    value={'schema':VERIFIED_SCHEMA if contract is not None else SCHEMA,'context':value,'pid':os.getpid(),
           'model_sha256':hashlib.sha256(model_bytes).hexdigest()}
    value|=extra
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0)
    with os.fdopen(os.open(path,flags,0o600),'w') as stream:
        stream.write(_encode(value));stream.flush();os.fsync(stream.fileno())


def validate(receipt,expected,task,*,pid=None):
    verified=expected.get('schema')==VERIFIED_SCHEMA
    keys={'schema','context','pid','model_sha256'}|({'rights_sha256','runtime'} if verified else set())
    if (not isinstance(receipt,dict) or set(receipt)!=keys
            or receipt['schema']!=(VERIFIED_SCHEMA if verified else SCHEMA) or receipt['context']!=context(task)
            or receipt['model_sha256']!=expected['model_sha256']
            or type(receipt['pid']) is not int or receipt['pid']<=0
            or (pid is not None and receipt['pid']!=pid)):
        raise ValueError('Original loaded-model receipt required')
    if verified and (receipt['rights_sha256']!=expected['rights_sha256'] or
                     _encode(receipt['runtime'])!=_encode(expected['rights']['runtime'])):
        raise ValueError('Original checkpoint rights and runtime receipt required')
    # Canonical JSON also prevents bool/int equivalence inside the context.
    if _encode(receipt['context'])!=_encode(context(task)):
        raise ValueError('Original model receipt context changed')
    return receipt
