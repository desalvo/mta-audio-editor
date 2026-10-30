"""Reviewed model descriptors and operator-owned runtime receipts, no user code."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

KINDS=frozenset({'audio-to-midi','audio-to-midi-basic-pitch','audio-to-midi-yourmt3','audio-to-midi-mr-mt3','audio-to-midi-transkun','vocal-harmony','vocal-synthesis'})
MODEL_SHA='2c3c1d144bfa61ad236e92e169c13535c880469a12a047d4e73451f2c059a0ec'


def root():
    from .runtime_paths import policy_paths
    path=policy_paths()[0]/'.studio-models'
    if path.is_symlink():raise ValueError('Unsafe studio model directory')
    path.mkdir(parents=True,exist_ok=True,mode=0o700)
    return path


def receipt():
    path=root()/'basic-pitch.json'
    if not path.is_file():return None
    if path.is_symlink() or path.stat().st_size>32768:raise ValueError('Unsafe model receipt')
    value=json.loads(path.read_text())
    runtime=root()/'basic-pitch-0.4.0-onnx-v1'
    python=runtime/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    model=runtime/str(value.get('model',''))
    if (value.get('version')!='0.4.0' or not model.resolve().is_relative_to(runtime.resolve())
            or model.is_symlink() or not python.is_file() or not model.is_file()
            or hashlib.sha256(model.read_bytes()).hexdigest()!=MODEL_SHA):
        raise ValueError('Model runtime integrity check failed')
    return {**value,'python':str(python),'runtime':str(runtime)}


def python_for(kind):
    if kind=='audio-to-midi-transkun':
        from .studio_asset_registry import catalog as managed
        return sys.executable if any(a.get('kind')=='transkun' and a.get('admitted') for a in managed()) else None
    if kind=='vocal-synthesis':
        from .vocal_banks import status
        from .studio_asset_registry import catalog as managed
        has_neural=any(v.get('admitted') and v.get('kind')=='diffsinger' for v in managed())
        if not has_neural and not any(v['installed'] for v in status()) and not os.getenv('MTA_DIFFSINGER_ROOT'):return None
        return sys.executable if not getattr(sys,'frozen',False) else os.getenv('MTA_AI_DEFAULT_PYTHON')
    if kind=='vocal-harmony':
        if not getattr(sys,'frozen',False):return sys.executable
        configured=os.getenv('MTA_AI_WORKER_VOCAL_HARMONY_PYTHON') or os.getenv('MTA_AI_DEFAULT_PYTHON')
        if configured:return configured
        local=receipt()
        return local['python'] if local else None
    if kind=='audio-to-midi-mr-mt3' or (kind=='audio-to-midi' and os.getenv('MTA_STUDIO_TRANSCRIBER')=='mr-mt3'):
        from .mrmt3_adapter import python_for as mrmt3_python
        interpreter=mrmt3_python()
        return str(interpreter) if interpreter else None
    if kind=='audio-to-midi-yourmt3' or (kind=='audio-to-midi' and os.getenv('MTA_STUDIO_TRANSCRIBER')=='yourmt3'):
        from .yourmt3_adapter import selected_variant, verified_runtime
        try:
            configured=verified_runtime(full=False)
            _,_,receipt_name=selected_variant()
            from .transcription_source_contract import read_json
            if read_json(configured/receipt_name).get('tested') is not True:return None
        except (ValueError,OSError,KeyError):return None
        return os.getenv('MTA_AI_WORKER_AUDIO_TO_MIDI_PYTHON')
    installed=receipt()
    return installed['python'] if installed and installed.get('enabled') else None


def available(kind):
    if kind=='vocal-harmony':return bool(python_for(kind))
    try:return bool(python_for(kind))
    except (ValueError,OSError):return False


def capabilities():
    error='';installed=None
    try:installed=receipt()
    except (OSError,ValueError) as exc:error=str(exc)
    from .vocal_banks import status as voice_status
    from .studio_asset_registry import catalog as asset_catalog
    return {'managed_assets':asset_catalog(),'voicebanks':voice_status(),'protocol':'mta-music-1','transcriber':os.getenv('MTA_STUDIO_TRANSCRIBER','basic-pitch'),'models':[
        {'id':'mr-mt3','kind':'audio-to-midi','version':'b8a3807e',
         'experimental':True,'display_name':'MR-MT3 (experimental)', 'available':available('audio-to-midi-mr-mt3'),
         'installed':bool(os.getenv('MTA_STUDIO_MRMT3_RUNTIME') and (Path(os.environ['MTA_STUDIO_MRMT3_RUNTIME'])/'mta-runtime.json').is_file()),
         'license':'MIT / Apache-2.0 T5 component','weights_license':'MIT (original-author pinned checkpoint)',
         'policy_model':'mr-mt3-assets','license_url':'https://github.com/gudgud96/MR-MT3',
         'sha256':'b8a3807ed265059abd25ad7f68142c06c35e8f6144dcaa45bd55946a3745398f',
         'capabilities':['multi-instrument-transcription','percussion'],'devices':['cpu','cuda','rocm'],'parameters':[],
         'requirements':{'device':'operator-configured','max_source_seconds':600,'operator_review':True},
         'notes':'Optional operator-installed runtime with strict tensor loading; component rights review required. No 10–16 instrument accuracy or calibrated confidence claim.'},
        {'id':'yourmt3','kind':'audio-to-midi','experimental':True,'display_name':'YourMT3+ (experimental)','version':'5e66c1ea','available':bool(python_for('audio-to-midi-yourmt3')),
         'installed':bool(os.getenv('MTA_STUDIO_YOURMT3_RUNTIME')),'license':'Apache-2.0','weights_license':'Apache-2.0 (original-author pinned Space)',
         'license_url':'https://huggingface.co/spaces/mimbres/YourMT3/tree/5e66c1ea173a8186e0d20432b841d3180cc015b5',
         'capabilities':['multi-instrument-transcription','percussion'],'compatibility_verified':['cpu-piano-fixture'],
         'devices':['cpu','cuda','rocm'],'parameters':[],'variants':['nops','ps'],'selected_variant':os.getenv('MTA_STUDIO_YOURMT3_VARIANT','nops'),
         'notes':'Experimental operator-verified runtime; no 10-16-instrument accuracy guarantee, calibrated confidence or dynamics; same-program players are merged'},
        {'id':'vocal-harmony','version':'1','capabilities':['midi-harmony'],'available':available('vocal-harmony'),'installed':True,
         'devices':['cpu'],'languages':[],'license':'EUPL-1.2','max_voices':8,'parameters':['voices','key','ranges','retain_melody'],
         'requirements':{'gpu':False},'notes':'Musical planner, not a singing synthesis model'},
        {'id':'basic-pitch','kind':'audio-to-midi','version':'0.4.0','capabilities':['isolated-source-transcription'],
         'available':bool(installed and installed.get('enabled')),'installed':bool(installed),'error':error,
         'devices':['cpu'],'compatibility_verified':['cpu'] if installed else [],'languages':[],
         'formats':{'input':['wav'],'output':['mta-music-1']},'sha256':MODEL_SHA,
         'size_bytes':installed.get('size_bytes',0) if installed else 0,'license':'Apache-2.0',
         'license_url':'https://github.com/spotify/basic-pitch/blob/main/LICENSE',
         'weights_license':'Apache-2.0 (included upstream ONNX model)',
         'dataset':'Not redistributed; see upstream ICASSP 2022 paper and model provenance',
         'requirements':{'device':'cpu','max_source_seconds':600,'memory':'model/sample-rate dependent; no calibrated RAM guarantee'},
         'parameters':['onset_threshold','frame_threshold','minimum_note_length','program'],
         'notes':'No instrument classifier, drums or calibrated note probabilities'}],
        'unavailable_candidates':[{'id':name,'available':False,'reason':'Backend, weights/voicebank rights and hardware validation required'}
             for name in ['Amphion','MT3','MT3-Infer']]}


def install_basic_pitch(cancelled,progress):
    """Explicit administrator action only. Publish receipt after real inference."""
    from .ai_project_lock import project_publication_lock
    from .storage import _atomic_json_write
    with project_publication_lock('studio-model:basic-pitch'):
        existing=receipt()
        if existing:return existing
        interpreter=[sys.executable] if sys.version_info[:2] in ((3,11),(3,12)) and not getattr(sys,'frozen',False) else None
        for name in ('python3.12','python3.11'):
            if not interpreter and shutil.which(name):interpreter=[shutil.which(name)]
        managed=None
        if not interpreter:
            bundled=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))/'tools'/('uv.exe' if os.name=='nt' else 'uv')
            managed=str(bundled) if bundled.is_file() else shutil.which('uv')
            if not managed:raise RuntimeError('Install Python 3.12/3.11 or the bundled uv runtime manager for Studio')
        runtime=root()/'basic-pitch-0.4.0-onnx-v1'
        if runtime.is_symlink():raise ValueError('Unsafe studio runtime')
        binary=runtime/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
        def run(command,phase):
            progress(phase)
            with (root()/'installation.log').open('ab') as log:
                process=subprocess.Popen(list(map(str,command)),stdout=log,stderr=log,stdin=subprocess.DEVNULL,start_new_session=os.name=='posix')
                deadline=time.monotonic()+1800
                try:
                    while process.poll() is None:
                        if cancelled():raise RuntimeError('Studio model installation cancelled')
                        if time.monotonic()>deadline:raise RuntimeError('Studio model installation timed out')
                        time.sleep(.1)
                    if process.returncode:raise RuntimeError('Studio model installation failed; inspect administrator installation log')
                finally:
                    from .studio_compute import terminate
                    terminate(process)
                    process.wait()
        if interpreter:run([*interpreter,'-m','venv',runtime],'creating-runtime')
        else:run([managed,'venv','--seed','--python','3.12','--managed-python',runtime],'creating-managed-python-runtime')
        pip=[binary,'-m','pip','install','--disable-pip-version-check']
        run([*pip,'-r',Path(__file__).resolve().parents[1]/'requirements-studio-basic-pitch.txt'],'installing-dependencies')
        run([*pip,'--no-deps','basic-pitch==0.4.0'],'installing-model')
        # This produces notes using the real ONNX backend, not merely an import.
        run([binary,Path(__file__).with_name('ai_studio_adapter.py'),'--self-test',runtime/'self-test.json'],'testing-model')
        test=json.loads((runtime/'self-test.json').read_text())
        model=Path(test['model_path'])
        if not model.resolve().is_relative_to(runtime.resolve()) or test.get('sha256')!=MODEL_SHA:
            raise RuntimeError('Installed model identity mismatch')
        value={'version':'0.4.0','enabled':True,'model':str(model.relative_to(runtime)),
               'size_bytes':sum(p.stat().st_size for p in runtime.rglob('*') if p.is_file() and not p.is_symlink()),
               'self_test':test,'installed_at':time.time()}
        if cancelled():raise RuntimeError('Installation cancelled before activation')
        _atomic_json_write(root()/'basic-pitch.json',value)
        return value


def test_basic_pitch(cancelled,progress):
    """A fresh inference test, not a replay of the installation receipt."""
    import tempfile
    from .ai_project_lock import project_publication_lock
    from .studio_compute import terminate
    from .storage import _atomic_json_write
    with project_publication_lock('studio-model:basic-pitch'):
        value=receipt()
        if not value:raise ValueError('Model not installed')
        with tempfile.TemporaryDirectory(prefix='mta-studio-test-') as raw:
            target=Path(raw)/'test.json'
            progress('testing-model')
            with (root()/'installation.log').open('ab') as log:
                process=subprocess.Popen([value['python'],str(Path(__file__).with_name('ai_studio_adapter.py')),
                    '--self-test',str(target)],stdin=subprocess.DEVNULL,stdout=log,stderr=log,
                    start_new_session=os.name=='posix',env={**os.environ,'ORT_DISABLE_TELEMETRY':'1'})
                deadline=time.monotonic()+180
                try:
                    while process.poll() is None:
                        if cancelled():raise RuntimeError('Model test cancelled')
                        if time.monotonic()>deadline:raise RuntimeError('Model test exceeded 180 seconds')
                        time.sleep(.1)
                    if process.returncode:raise RuntimeError('Model inference test failed; inspect installation log')
                finally:terminate(process)
            test=json.loads(target.read_text())
            if test.get('sha256')!=MODEL_SHA or test.get('notes',0)<1:raise RuntimeError('Invalid model test result')
            value['self_test']={**test,'tested_at':time.time()}
            value.pop('python',None);value.pop('runtime',None)
            _atomic_json_write(root()/'basic-pitch.json',value)
            return value['self_test']
