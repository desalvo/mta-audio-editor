#!/usr/bin/env python3
"""Trusted optional inference backends for the metered AI worker subprocess protocol.

Install this file only through the operator-controlled worker registry. Heavy model
libraries are imported lazily. All paths originate in the private job directory.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path
import sys
# Subprocess starts in the isolated job workspace, not the repository.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SUPPORTED = {'whisper', 'chords-ml', 'demucs', 'drumsep', 'sam-audio', 'singer-separation', 'backing-vocals', 'markers'}


def _backend_command(plan, folder, backend, arguments):
    from app.ai_torch_diagnostics import enabled
    python=sys.executable
    if backend=='demucs':
        from app.demucs_runtime import python_path
        configured=python_path()
        if configured is not None:python=str(configured)
    if enabled() or __import__('app.ai_gpu_verified',fromlist=['readiness']).readiness()['ready']:
        return [python, str(Path(__file__).with_name('ai_profiled_backend.py')),
                '--backend', backend, '--task-id', str(plan.get('gpu_profile_task_id', '')),
                '--report-dir', str(folder), '--', *arguments]
    if backend == 'demucs':
        return [python, '-m', 'demucs.separate', *arguments]
    return [sys.executable, str(Path(__file__).with_name('sam_audio_worker.py')), *arguments]


def _artifacts(folder: Path, entries: list[tuple[Path, str]]) -> None:
    """Publish a complete manifest only after every output is validated.

    Never expose a partial manifest to the packaging consumer; it would make a
    crashed adapter appear to have finished and could lose or misbill outputs.
    """
    from app.ai_worker_artifacts import MAX_FILES, MAX_ARTIFACT_BYTES, SAFE_NAME
    from app.ai_payload_limits import worker_artifact_bytes
    budget = worker_artifact_bytes(MAX_ARTIFACT_BYTES)
    if not 1 <= len(entries) <= MAX_FILES:
        raise RuntimeError('Invalid number of worker artifacts')
    folder = folder.resolve(strict=True)
    manifest = []
    seen: set[str] = set()
    total = 0
    for path, media in entries:
        if (not SAFE_NAME.fullmatch(path.name) or path.name.startswith('.')
                or path.name in seen or media not in {'audio/wav', 'application/json', 'text/plain'}):
            raise RuntimeError('Unsafe or duplicate worker artifact')
        if ((media == 'audio/wav' and path.suffix != '.wav')
                or (media == 'application/json' and path.suffix != '.json')):
            raise RuntimeError('Invalid worker artifact extension')
        if path.parent.resolve() != folder or path.is_symlink():
            raise RuntimeError('Worker output must remain inside job workspace')
        try:
            info = path.stat()
        except OSError as exc:
            raise RuntimeError('Worker output is not available') from exc
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise RuntimeError('Worker output must be an unlinked regular file')
        total += info.st_size
        if total > budget:
            raise RuntimeError('Worker outputs exceed artifact size limit')
        # Hash the validated inode; packaging verifies the same bytes before delivery.
        from app.ai_worker_artifacts import _read_private_file
        snapshot = _read_private_file(path, budget - (total - info.st_size))
        seen.add(path.name)
        manifest.append({'name': path.name, 'type': media, 'sha256': hashlib.sha256(snapshot).hexdigest()})
    # Atomic replacement keeps consumer reads all-or-nothing, including when
    # an adapter process dies in the middle of writing the JSON manifest.
    data = json.dumps({'version': 1, 'files': manifest}, separators=(',', ':')).encode('utf-8')
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(mode='wb', prefix='.manifest-', suffix='.tmp',
                                         dir=folder, delete=False) as handle:
            temp_name = handle.name
            os.fchmod(handle.fileno(), 0o600)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, folder / 'output.manifest.json')
        temp_name = None
        if hasattr(os, 'O_DIRECTORY'):
            fd = os.open(folder, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
    finally:
        if temp_name is not None:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass


def infer(plan: dict, output: Path) -> None:
    kind = plan.get('kind')
    if kind not in SUPPORTED:
        raise ValueError('Unsupported unified inference backend')
    # Resolve only the trusted job directory. Never follow a caller-controlled
    # source symlink out of that directory, even when it points back inside.
    folder = output.parent.resolve(strict=True)
    raw_source = Path(str(plan.get('source_audio', '')))
    source = folder / 'source.wav'
    if (raw_source != source or source.is_symlink() or source.parent != folder
            or not source.is_file()):
        raise ValueError('Audio must be staged into the private job workspace')
    # A hard link can escape the private-workspace boundary even when its path
    # is local and is_symlink() returns False. Reject shared inodes.
    source_info = source.stat()
    if not stat.S_ISREG(source_info.st_mode) or source_info.st_nlink != 1:
        raise ValueError('Audio source must be an exclusive regular file')
    if kind == 'whisper':
        from app.music_text import extract_lyrics
        lines = extract_lyrics(source, model_name=str(plan.get('model') or 'turbo'),
                              language=plan.get('language') or None,
                              advanced_alignment=bool(plan.get('advanced_alignment', False)),require_inprocess=True)
        result = folder / 'transcript.json'
        result.write_text(json.dumps({'lines': [v.model_dump(mode='json') for v in lines]}, ensure_ascii=False), encoding='utf-8')
        _artifacts(folder, [(result, 'application/json')]); return
    if kind == 'chords-ml':
        from app.music_text import extract_chords_progressive
        chords = extract_chords_progressive(source,engine=plan.get('engine') or __import__('app.ai_models',fromlist=['chords_catalog']).chords_catalog(native=False)['default_engine'],options=plan.get('options'),bpm=float(plan.get('bpm',120)),beat_origin_ms=int(plan.get('beat_origin_ms',0)))
        result = folder / 'chords.json'
        result.write_text(json.dumps({'chords': [v.model_dump(mode='json') for v in chords]}, ensure_ascii=False), encoding='utf-8')
        _artifacts(folder, [(result, 'application/json')]); return
    if kind == 'markers':
        from app.music_text import extract_markers
        result=folder/'markers.json'
        events=extract_markers(source)
        result.write_text(json.dumps({'markers':[v.model_dump(mode='json') for v in events]}))
        _artifacts(folder,[(result,'application/json')]);return
    if kind == 'drumsep':
        from app.drumsep_onnx_worker import infer as drumsep_infer
        configured = os.environ.get('MTA_AI_DRUMSEP_MODEL', '')
        if configured:
            model = Path(configured)
        else:
            # Same upstream URL and SHA-256 validation as the native model manager.
            from app.main import _DRUMSEP_PATH, _download_drumsep_model
            model = _DRUMSEP_PATH
            if not model.is_file():
                _download_drumsep_model()
        if not model.is_file():
            raise RuntimeError('Configured DrumSep checkpoint is unavailable')
        paths = drumsep_infer(source, model, folder)
        _artifacts(folder, [(p, 'audio/wav') for p in paths]); return
    if kind == 'sam-audio':
        from app.sam_audio_worker import main as _unused  # noqa: F401
        import subprocess
        model = str(plan.get('model') or os.environ.get('MTA_AI_SAM_MODEL', ''))
        if model in {'sam-audio-small','sam-audio-base','sam-audio-large'}:model='facebook/'+model
        if not model: raise RuntimeError('Operator must configure MTA_AI_SAM_MODEL')
        if plan.get('model') and model not in {'facebook/sam-audio-small','facebook/sam-audio-base','facebook/sam-audio-large'}:raise ValueError('Unsupported SAM model')
        target = folder / 'separated.wav'
        arguments=['--source',str(source),'--output',str(target),'--model',model,'--prompt',str(plan.get('prompt') or 'vocals')]
        if plan.get('anchors'):arguments+=['--anchors-json',json.dumps(plan['anchors'])]
        subprocess.run(_backend_command(plan,folder,'sam-audio',arguments),check=True)
        _artifacts(folder, [(target, 'audio/wav')]); return
    if kind == 'demucs':
        import subprocess
        model = str(plan.get('model') or 'htdemucs')
        if not model.replace('_', '').replace('-', '').isalnum() or len(model) > 64:
            raise ValueError('Invalid Demucs model')
        from app.demucs_runtime import device_arguments
        count=plan.get('stem_count',0)
        if type(count) is not int or (count!=0 and not 2<=count<=64):raise ValueError('Invalid stem count')
        arguments=['--name', model, '--out', str(folder/'demucs'), *device_arguments()]
        if count==2:arguments+=['--two-stems','vocals']
        subprocess.run(_backend_command(plan, folder, 'demucs', [*arguments,str(source)]), check=True)
        paths = sorted((folder/'demucs'/model/source.stem).glob('*.wav'))
        if not paths: raise RuntimeError('Demucs produced no stems')
        staged=[]
        for p in paths:
            dest = folder / ('stem_' + p.name)
            p.replace(dest); staged.append((dest, 'audio/wav'))
        _artifacts(folder, staged); return
    if kind == 'singer-separation':
        import subprocess
        singers = plan.get('singers')
        selected = plan.get('selected','all')
        model = str(plan.get('model') or 'sam-audio-small')
        if model not in {'sam-audio-small','sam-audio-base','sam-audio-large'} or not isinstance(singers,list) or not 2<=len(singers)<=8:
            raise ValueError('Invalid singer separation parameters')
        required = {'singer_'+str(i) for i in range(1,len(singers)+1)}
        if selected!='all' and selected not in required: raise ValueError('Unknown singer target')
        for index, item in enumerate(singers,1):
            if not isinstance(item,dict) or item.get('id')!='singer_'+str(index):
                raise ValueError('Invalid singer identifier')
            if not all(isinstance(item.get(k),(int,float)) for k in ('start','end')) or not 0<=item['start']<item['end']<=86400:
                raise ValueError('Invalid singer interval')
        files=[]
        for singer in singers:
            if selected!='all' and selected!=singer['id']:continue
            anchors=[['+',singer['start'],singer['end']]]+[['-',v['start'],v['end']] for v in singers if v['id']!=singer['id']]
            result=folder/(singer['id']+'.wav')
            subprocess.run(_backend_command(plan,folder,'sam-audio',['--source',str(source),'--output',str(result),
                            '--model','facebook/'+model,'--prompt','singing voice',
                            '--anchors-json',json.dumps(anchors)]),check=True)
            files.append((result,'audio/wav'))
        _artifacts(folder,files)
        return
    if kind == 'backing-vocals':
        # A configured audio-separator model is mandatory; no DSP fallback is silently billed as AI.
        from audio_separator.separator import Separator
        from app.ai_backend_models import LEAD_BACKING_MODELS
        chosen=plan.get('model')
        known={m['id']:m['filename'] for m in LEAD_BACKING_MODELS}
        if chosen and chosen not in known:raise ValueError('Unsupported backing-vocal model')
        model = known[chosen] if chosen else os.environ.get('MTA_AI_VOCAL_MODEL', '')
        if not model or '/' in model or '\\' in model:
            raise RuntimeError('Operator must configure a safe MTA_AI_VOCAL_MODEL filename')
        separator = Separator(output_dir=str(folder), output_format='WAV', model_file_dir=os.environ.get('MTA_LEAD_BACKING_MODEL_DIR', os.environ.get('MTA_AI_VOCAL_MODELS_DIR', '')))
        from app.backing_vocals_runtime import load_backing_model
        load_backing_model(separator, model)
        names = separator.separate(str(source))
        paths=[]
        for index, name in enumerate(names):
            source_path = Path(name)
            if not source_path.is_absolute(): source_path = folder/source_path
            if source_path.resolve().parent != folder or not source_path.is_file():
                raise RuntimeError('Unexpected output path from separator')
            label='backing' if any(v in source_path.name.lower() for v in ('instrumental','karaoke','backing')) else ('lead' if 'vocal' in source_path.name.lower() else 'voice')
            dest=folder/f'{label}_{index}.wav'
            source_path.replace(dest); paths.append((dest, 'audio/wav'))
        if not paths: raise RuntimeError('Separator produced no audio')
        _artifacts(folder, paths)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.request.read_text(encoding='utf-8'))
    from app.ai_torch_diagnostics import profile_call
    # Child backends must profile themselves. Never profile the idle parent
    # waiting for Demucs/SAM; one singer report covers only its own invocation.
    if data.get('kind') in ('demucs', 'sam-audio', 'singer-separation'):
        infer(data, args.output)
    else:
        profile_call(args.output.parent, str(data.get('gpu_profile_task_id', '')),
                     lambda: infer(data, args.output))


if __name__ == '__main__':
    main()
