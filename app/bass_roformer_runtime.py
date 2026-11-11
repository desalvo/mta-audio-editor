"""Opt-in ZFTurbo four-stem checkpoint; never loads SW or downloads on inference."""
import hashlib
import os
from pathlib import Path
import shutil
import tempfile

CHECKPOINT_SHA256 = '3e9daecd70aaed5b5a0d1f861cc4d77eaa45afb3fc6301b1cf32c1be0f5868fb'
POLICY = 'bs-roformer-zfturbo'
MODELS = {'bs-roformer-bass': 2, 'bs-roformer-4stem': 4}
LABELS = ('drums', 'bass', 'other', 'vocals')


def managed_checkpoint():
    from .auth import data_root
    return data_root() / 'models' / 'bass-roformer' / 'v1.0.12.ckpt'


def verify_checkpoint(path):
    path = Path(path)
    from .bass_roformer_install import WEIGHTS
    if not path.is_absolute() or path.is_symlink() or not path.is_file() or path.stat().st_size != WEIGHTS[1]:
        raise ValueError('BS RoFormer checkpoint missing or invalid size')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    if digest.hexdigest() != CHECKPOINT_SHA256:
        raise ValueError('BS RoFormer checkpoint SHA-256 mismatch')
    return path


def configured():
    from .bass_roformer_install import receipt
    state = receipt()
    return bool(state and state['checkpoint_validated'] and managed_checkpoint().is_file()
                and not managed_checkpoint().is_symlink())


def profiles():
    ready = configured()
    return [{'id': model, 'model': model, 'stem_count': count,
             'display_name': 'BS RoFormer ZFTurbo · ' + ('Bass + accompaniment' if count == 2 else '4 stems'),
             'stem_labels': ['bass', 'accompaniment'] if count == 2 else list(LABELS),
             'engine': 'bs_roformer', 'installed': ready, 'license_policy': POLICY,
             'checkpoint_sha256': CHECKPOINT_SHA256}
            for model, count in MODELS.items()]


def validate_options(model, stem_count=0):
    if model not in MODELS or type(stem_count) is not int or stem_count not in (0, MODELS[model]):
        raise ValueError('BS RoFormer requires Auto or the selected profile stem count')


def prepare_track_source(project, track, source, directory, start_ms=0, end_ms=None, cancel_event=None):
    """Render edits/inserts before optional cropping; preserve timeline coordinates."""
    from .audio_engine import render_track
    from .separator_process import run
    from .ai_execution_policy import isolated_env
    if type(start_ms) is not int or start_ms < 0 or (end_ms is not None and (type(end_ms) is not int or end_ms <= start_ms)):
        raise ValueError('Invalid separation interval')
    directory = Path(directory)
    rendered = directory / 'edited-source.wav'
    render_track(track, source, rendered, sample_rate=project.sample_rate)
    if start_ms == 0 and end_ms is None: return rendered
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg: raise RuntimeError('FFmpeg is required for interval separation')
    cropped = directory / 'selected-source.wav'
    command = [ffmpeg, '-v', 'error', '-nostdin', '-i', str(rendered), '-ss', str(start_ms / 1000)]
    if end_ms is not None: command += ['-t', str((end_ms - start_ms) / 1000)]
    command += ['-c:a', 'pcm_f32le', str(cropped)]
    run(command, cancel_event=cancel_event, env=isolated_env())
    return cropped


def infer(source, output_dir, model='bs-roformer-bass', *, stem_count=0, progress=None, cancel_event=None):
    from .model_license_policy import evaluate_model, guarded_model_call
    from .ai_execution_policy import isolated_env
    from .bass_roformer_install import receipt
    from .separator_process import run
    validate_options(model, stem_count)
    evaluate_model(POLICY)
    state = receipt()
    if not state or not state['checkpoint_validated']:
        raise RuntimeError('Install BS RoFormer ZFTurbo from administrator AI Models on the executing worker')
    checkpoint = verify_checkpoint(managed_checkpoint())
    source = Path(source).resolve(strict=True)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        raise RuntimeError('FFmpeg is required for BS RoFormer input conversion')
    with tempfile.TemporaryDirectory(prefix='mta-bass-') as work:
        work = Path(work)
        inputs, outputs = work / 'inputs', work / 'outputs'
        inputs.mkdir(); outputs.mkdir()
        staged = inputs / 'mta_input.wav'
        if progress: progress(20, 'BS RoFormer: preparing audio')
        guarded_model_call(POLICY, run,
            [ffmpeg, '-v', 'error', '-nostdin', '-i', str(source), '-ar', '44100', '-ac', '2',
             '-c:a', 'pcm_f32le', str(staged)], cancel_event=cancel_event, env=isolated_env())
        command = [str(state['python']), str(state['root'] / 'inference.py'), '--model_type', 'bs_roformer',
                   '--config_path', str(state['config']), '--start_check_point', str(checkpoint),
                   '--input_folder', str(inputs), '--store_dir', str(outputs), '--pcm_type', 'FLOAT',
                   '--filename_template', '{instr}']
        # Respect the explicitly installed CPU mode even if this node has CUDA.
        if state.get('device') == 'cpu': command.append('--force_cpu')
        if progress: progress(35, 'BS RoFormer: separating bass')
        guarded_model_call(POLICY, run, command, cwd=state['root'], cancel_event=cancel_event,
                           env=isolated_env())
        import numpy as np
        import soundfile as sf
        original, rate = sf.read(staged, dtype='float32', always_2d=True)
        if not original.size or not np.isfinite(original).all():
            raise RuntimeError('BS RoFormer input contains empty or nonfinite audio')
        chosen = LABELS if model == 'bs-roformer-4stem' else ('bass',)
        audio = {}
        for label in chosen:
            path = outputs / (label + '.wav')
            if path.is_symlink() or not path.is_file():
                raise RuntimeError('BS RoFormer output missing: ' + label)
            data, sr = sf.read(path, dtype='float32', always_2d=True)
            if sr != rate or data.shape != original.shape or not np.isfinite(data).all():
                raise RuntimeError('BS RoFormer output length, channels or samples invalid: ' + label)
            audio[label] = data
        if model == 'bs-roformer-bass':
            # Subtract in float, never normalize stems independently: their sum
            # must retain the original mix, including any separator residual.
            with np.errstate(over='ignore', invalid='ignore'):
                audio['accompaniment'] = original - audio['bass']
            if not np.isfinite(audio['accompaniment']).all():
                raise RuntimeError('BS RoFormer accompaniment contains nonfinite audio')
        evaluate_model(POLICY)
        if cancel_event is not None and cancel_event.is_set():
            raise RuntimeError('stem separation cancelled')
        return _publish_audio(audio, rate, output_dir, progress, cancel_event)


def _publish_audio(audio, rate, output_dir, progress, cancel_event):
    """Stage the complete output set; roll back owned files on any failure.

    Exclusive hard links publish complete WAVs without overwriting a file that
    appears after preflight. Callers register the set only after this returns.
    """
    import soundfile as sf
    from .model_license_policy import evaluate_model

    paths = [output_dir / (label + '.wav') for label in audio]
    if any(path.exists() or path.is_symlink() for path in paths):
        raise ValueError('BS RoFormer output already exists')
    with tempfile.TemporaryDirectory(prefix='.mta-stems-', dir=output_dir) as work:
        staged = [Path(work) / path.name for path in paths]
        for path, data in zip(staged, audio.values()):
            sf.write(path, data, rate, subtype='FLOAT')
        published = []
        try:
            for source, target in zip(staged, paths):
                evaluate_model(POLICY)
                if cancel_event is not None and cancel_event.is_set():
                    raise RuntimeError('stem separation cancelled')
                os.link(source, target)
                published.append((source, target))
            evaluate_model(POLICY)
            if cancel_event is not None and cancel_event.is_set():
                raise RuntimeError('stem separation cancelled')
            if progress: progress(88, 'BS RoFormer: separation complete')
            return paths
        except BaseException:
            for source, target in published:
                _remove_owned_output(source, target)
            raise


def _remove_owned_output(source, target):
    try:
        current = target.lstat()
    except FileNotFoundError:
        return
    original = source.stat()
    if (current.st_dev, current.st_ino) == (original.st_dev, original.st_ino):
        target.unlink(missing_ok=True)
