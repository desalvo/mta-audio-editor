"""Private, integrity-checked checkpoints for completed, metered inference stages."""
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import zipfile
import zlib
from pydantic import ValidationError
from .music_interchange import parse_result


def fingerprint(kind,plan=None):
    """Invalidate recovery when the selected model/runtime/adapter changes."""
    from .model_license_policy import evaluate
    from .ai_worker_registry import resolve_worker
    from .studio_catalog import root
    if os.getenv('MTA_NATIVE_SINGLE_USER','').lower()=='true':
        from .native_ai_routing import is_remote,_read
        operation='audio-to-midi' if kind.startswith('audio-to-midi-') else kind
        if is_remote(operation):
            from .ai_remote_client import studio_capabilities
            cfg=_read()['workers'][operation]
            value={'server':cfg['url'],'account':hashlib.sha256(cfg['token'].encode()).hexdigest(),
                   'studio':studio_capabilities(cfg['url'],cfg['token'])}
            return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
    if kind=='audio-to-midi':kind='audio-to-midi-'+os.getenv('MTA_STUDIO_TRANSCRIBER','basic-pitch')
    values={'version':1,'kind':kind,'environment':{key:value for key,value in os.environ.items()
            if key.startswith(('MTA_STUDIO_','MTA_AI_WORKER_')) and not any(s in key for s in ('TOKEN','SECRET','PASSWORD'))}}
    # Cache keys contain hashes only, never raw deployment settings.
    worker=resolve_worker(kind)
    if worker and worker.is_file():values['adapter']=hashlib.sha256(worker.read_bytes()).hexdigest()
    for name in ('ai_studio_adapter.py','studio_parameters.py','music_interchange.py',
                 'yourmt3_adapter.py','mrmt3_adapter.py','mrmt3_decode.py','transcription_timing.py','transkun_adapter.py','transkun_runner.py','demucs_runtime.py'):
        path=Path(__file__).with_name(name)
        if path.is_file():values['source:'+name]=hashlib.sha256(path.read_bytes()).hexdigest()
    files=[root()/'basic-pitch.json'] if kind.endswith('basic-pitch') else []
    if kind.endswith('yourmt3'):
        from .yourmt3_adapter import selected_variant
        files.append(Path(os.environ.get('MTA_STUDIO_YOURMT3_RUNTIME',''))/selected_variant()[2])
    if kind.endswith('mr-mt3'):
        files.append(Path(os.environ.get('MTA_STUDIO_MRMT3_RUNTIME',''))/'mta-runtime.json')
    for file in files:
        if file.is_file() and not file.is_symlink():
            values[str(file)]=hashlib.sha256(file.read_bytes()).hexdigest()
    asset_id=(plan or {}).get('options',{}).get('asset_id')
    if asset_id:
        from .studio_asset_registry import manifest
        m=manifest(asset_id);values['asset_manifest']=hashlib.sha256((m['folder']/'manifest.json').read_bytes()).hexdigest()
    if kind=='demucs':
        from .demucs_runtime import python_path,checkpoint_fingerprints
        binary=python_path()
        if binary:values['demucs_python']=hashlib.sha256(binary.read_bytes()).hexdigest()
        values['demucs_hf_snapshot']=checkpoint_fingerprints((plan or {}).get('model','htdemucs'))
        cache=Path(os.getenv('TORCH_HOME',str(Path.home()/'.cache'/'torch')))/'hub'/'checkpoints'
        for path in sorted(cache.glob('*.th')) if cache.is_dir() else []:
            if path.is_file() and not path.is_symlink():
                with path.open('rb') as stream:values['weights:'+path.name]=hashlib.file_digest(stream,'sha256').hexdigest()
    values['policy']=evaluate(kind,plan or ({'model':'htdemucs'} if kind=='demucs' else {})).policy_sha256
    return hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()


class StageCache:
    def __init__(self,directory,previous=None,dependency=fingerprint):
        self.directory=Path(directory);self.previous=Path(previous) if previous else None
        if self.directory.is_symlink() or (self.previous and self.previous.is_symlink()):
            raise ValueError('Unsafe inference checkpoint directory')
        self.directory.mkdir(parents=True,exist_ok=True,mode=0o700)
        if not self.directory.is_dir() or self.directory.is_symlink():
            raise ValueError('Unsafe inference checkpoint directory')
        self.dependency=dependency

    def key(self,kind,plan,audio,artifact_mode):
        # Re-evaluate at each stage boundary: a long-lived cache object must not
        # reuse checkpoints after a model, policy, or runtime changes in-process.
        value={'kind':kind,'plan':plan,'audio_sha256':hashlib.sha256(audio).hexdigest(),
               'artifact_mode':artifact_mode,'dependency':self.dependency(kind,plan)}
        return hashlib.sha256(json.dumps(value,sort_keys=True,allow_nan=False).encode()).hexdigest()

    def _read(self,directory,key,artifact_mode):
        from .ai_worker_artifacts import _read_private_file
        from .ai_payload_limits import worker_artifact_bytes,MAX_ARTIFACT_BYTES
        from .studio_compute import stem_artifacts
        path=directory/(key+'.zip')
        if path.is_symlink():raise ValueError('Unsafe inference checkpoint link')
        if not path.exists():return None
        try:
            raw=_read_private_file(path,worker_artifact_bytes(MAX_ARTIFACT_BYTES)+1024*1024)
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                if len(archive.infolist())!=2 or set(archive.namelist())!={'receipt.json','result'}:return None
                receipt=archive.getinfo('receipt.json');data=archive.getinfo('result')
                if receipt.file_size>4096 or data.file_size>worker_artifact_bytes(MAX_ARTIFACT_BYTES):return None
                metadata=json.loads(archive.read(receipt));payload=archive.read(data)
                if metadata!={'schema':'mta-studio-stage-1','key':key,'sha256':hashlib.sha256(payload).hexdigest()}:return None
                return stem_artifacts(payload) if artifact_mode=='stems' else parse_result(payload)
        except (ValueError, OSError, KeyError, EOFError, RuntimeError, zlib.error,
                ValidationError, json.JSONDecodeError, zipfile.BadZipFile):
            # A damaged/incompatible checkpoint must trigger a fresh real stage,
            # never turn stored bytes into a successful recovered inference.
            return None

    def _write(self,key,result,artifact_mode):
        from .fs_durability import sync_directory
        if artifact_mode=='stems':
            buffer=io.BytesIO()
            with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_DEFLATED) as archive:
                for name,data in result.items():archive.writestr(name,data)
            payload=buffer.getvalue()
        else:
            # Do not durably acknowledge a malformed or out-of-contract result.
            # An invalid result must be fixed at its real inference source, not cached.
            payload=result.model_dump_json().encode()
            parse_result(payload)
        receipt={'schema':'mta-studio-stage-1','key':key,'sha256':hashlib.sha256(payload).hexdigest()}
        target=self.directory/(key+'.zip')
        if target.is_symlink():raise ValueError('Unsafe inference checkpoint')
        fd,name=tempfile.mkstemp(prefix='.stage-',dir=self.directory)
        try:
            with os.fdopen(fd,'w+b') as stream:
                with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_STORED) as archive:
                    archive.writestr('receipt.json',json.dumps(receipt));archive.writestr('result',payload)
                stream.flush();os.fsync(stream.fileno())
            os.replace(name,target);sync_directory(self.directory)
        finally:Path(name).unlink(missing_ok=True)

    def execute(self,compute,user_id,kind,plan,*,audio,artifact_mode='music',**kwargs):
        key=self.key(kind,plan,audio,artifact_mode)
        for directory in [self.directory,*([self.previous] if self.previous else [])]:
            result=self._read(directory,key,artifact_mode)
            if result is not None:
                if directory!=self.directory:self._write(key,result,artifact_mode)
                return result,{'usage':{},'recovered':True}
        result,meta=compute(user_id,kind,plan,audio=audio,artifact_mode=artifact_mode,**kwargs)
        # Durably preserve validated output before acknowledging remote success.
        self._write(key,result,artifact_mode)
        callback=meta.get('acknowledge')
        if callable(callback):callback()
        return result,{k:v for k,v in meta.items() if k!='acknowledge'}
