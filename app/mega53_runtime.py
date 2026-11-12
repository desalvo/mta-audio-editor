"""Opt-in MVSep Mega 53 lead/back adapter; uses an operator-installed upstream runtime.

This never downloads or silently substitutes checkpoints. The operator must supply
an absolute upstream checkout, matching YAML and checkpoint and review their rights.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import shutil
import hashlib

# Original 53-stem v1.0.21 checkpoint; never trust a same-named replacement.
MEGA53_V1_SHA256 = "c62820893bbf86d4e734f966bd142d9157cfc8bb8e79e9d8f9ea553f3ff3519f"

def verify_mega53_checkpoint(path):
    path = _verified_file(str(path), "checkpoint")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != MEGA53_V1_SHA256:
        raise RuntimeError("Mega 53 checkpoint SHA-256 mismatch: only v1.0.21 original weights are admitted")
    return path


def _verified_file(value, label):
    path = Path(value).expanduser()
    if not path.is_absolute() or not path.is_file() or path.is_symlink():
        raise RuntimeError(f'Mega 53 requires a regular absolute {label} file')
    return path.resolve()


def _verified_directory(value):
    path = Path(value).expanduser()
    if not path.is_absolute() or not path.is_dir() or path.is_symlink():
        raise RuntimeError('Mega 53 requires a local absolute upstream directory')
    if not (path / 'inference.py').is_file():
        raise RuntimeError('Mega 53 upstream inference.py not found')
    return path.resolve()


def managed_checkpoint():
    from .auth import data_root
    return data_root() / 'models' / 'mega53' / 'v1.0.21.ckpt'


def configured():
    checkpoint = os.getenv('MTA_MEGA53_CHECKPOINT') or (str(managed_checkpoint()) if managed_checkpoint().is_file() else '')
    from .mega53_install import receipt
    managed = receipt()
    return bool((os.getenv('MTA_MEGA53_ROOT') or managed) and (os.getenv('MTA_MEGA53_CONFIG') or managed) and checkpoint)


def _required_setting(name):
    value = os.getenv(name, '').strip()
    if not value and name in ('MTA_MEGA53_ROOT', 'MTA_MEGA53_CONFIG', 'MTA_MEGA53_PYTHON'):
        from .mega53_install import receipt
        managed = receipt()
        key = {'MTA_MEGA53_ROOT': 'root', 'MTA_MEGA53_CONFIG': 'config', 'MTA_MEGA53_PYTHON': 'python'}[name]
        if managed: value = str(managed[key])
    if not value and name == 'MTA_MEGA53_CHECKPOINT' and managed_checkpoint().is_file():
        value = str(managed_checkpoint())
    if not value:
        raise RuntimeError(
            'Mega 53 runtime upstream non configurato nel processo che esegue il worker: '
            f'impostare {name} insieme a MTA_MEGA53_ROOT, MTA_MEGA53_CONFIG e '
            'MTA_MEGA53_CHECKPOINT; consultare la guida amministratore.'
        )
    return value


def check_local_configuration():
    """Check configured paths on this worker, without loading or hashing weights."""
    _verified_directory(_required_setting('MTA_MEGA53_ROOT'))
    _verified_file(_required_setting('MTA_MEGA53_CONFIG'), 'config')
    _verified_file(_required_setting('MTA_MEGA53_CHECKPOINT'), 'checkpoint')
    try: python = _required_setting('MTA_MEGA53_PYTHON')
    except RuntimeError: python = sys.executable
    _verified_file(python, 'Python interpreter')


def infer(source, output_dir, cancel_event=None, drum_targets=None):
    """Return canonical (lead, backing) WAVs; fail closed on ambiguous outputs."""
    from .model_license_policy import evaluate_model,guarded_model_call
    evaluate_model('mvsep-mega53')
    root = _verified_directory(_required_setting('MTA_MEGA53_ROOT'))
    config = _verified_file(_required_setting('MTA_MEGA53_CONFIG'), 'config')
    checkpoint = verify_mega53_checkpoint(_required_setting('MTA_MEGA53_CHECKPOINT'))
    try: python_setting = _required_setting('MTA_MEGA53_PYTHON')
    except RuntimeError: python_setting = sys.executable
    python = _verified_file(python_setting, 'Python interpreter')
    source = _verified_file(str(source), 'source audio')
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='mta-mega53-') as work:
        work = Path(work)
        inputs, outputs = work / 'inputs', work / 'outputs'
        inputs.mkdir(); outputs.mkdir()
        shutil.copyfile(source, inputs / ('mta_input' + source.suffix))
        # Keep the explicitly configured upstream root importable without
        # inheriting PYTHONPATH/user-site or Python/linker startup injection.
        bootstrap = ('import runpy,sys;sys.path.insert(0,sys.argv[1]);'
                     'sys.argv=sys.argv[2:];runpy.run_path(sys.argv[0],run_name="__main__")')
        cmd = [str(python), '-I', '-c', bootstrap, str(root), str(root / 'inference.py'), '--model_type', 'bs_roformer',
               '--config_path', str(config), '--start_check_point', str(checkpoint),
               '--input_folder', str(inputs), '--store_dir', str(outputs)]
        from .separator_process import run
        from .ai_execution_policy import isolated_env
        try:guarded_model_call('mvsep-mega53',run,cmd,cwd=root,cancel_event=cancel_event,env=isolated_env())
        except (RuntimeError,subprocess.SubprocessError) as exc:
            raise RuntimeError('Mega 53 inference failed: '+str(exc)) from exc
        # Exact tokens prevent a source labelled "snare" matching some unrelated artifact.
        names = ('kick', 'snare', 'hh', 'toms', 'drums', 'percussion') if drum_targets is not None else ('lead-vocal', 'back-vocal')
        stems = {name: [] for name in names}
        for candidate in outputs.rglob('*.wav'):
            if candidate.is_symlink() or not candidate.is_file():
                continue
            normalized = candidate.stem.lower().replace('_', '-').replace(' ', '-')
            for name in names:
                if normalized == name or normalized.startswith(name + '-') or normalized.endswith('-' + name):
                    stems[name].append(candidate)
        if drum_targets is not None:
            # Mega 53 has no single cymbals target: hi-hat and other cymbals
            # must never be silently represented as equivalent.
            if not drum_targets or not drum_targets <= {'kick', 'snare', 'toms', 'hh', 'drums', 'percussion'}:
                raise RuntimeError('Unsupported Mega 53 drum target')
            results = {}
            for name in sorted(drum_targets):
                if len(stems[name]) != 1:
                    raise RuntimeError(f'Mega 53 drum output missing or ambiguous: {name}')
                name_out = {'percussion': 'percussions', 'drums': 'drums_without_percussions'}.get(name, name) + '.wav'
                results[name_out] = stems[name][0]
            return _publish_outputs(results, out, cancel_event, local=True)
        if any(len(stems[name]) != 1 for name in ('lead-vocal', 'back-vocal')):
            raise RuntimeError('Mega 53 outputs missing or ambiguous: lead-vocal and back-vocal required')
        lead, backing = _publish_outputs({'lead_vocals.wav': stems['lead-vocal'][0],
                                         'backing_vocals.wav': stems['back-vocal'][0]},
                                        out, cancel_event, local=True)
        return lead, backing, 'mvsep-mega53'


def _publish_outputs(entries, output_dir, cancel_event, *, local=False):
    """Publish a complete group without replacing files; roll back owned links.

    Remote admission belongs to the executing worker. Local inference must also
    recheck its policy during publication. This is not a crash-atomic group.
    """
    from .model_license_policy import evaluate_model
    def admit():
        if cancel_event is not None and cancel_event.is_set():
            raise RuntimeError('stem separation cancelled')
        if local:
            evaluate_model('mvsep-mega53')
    admit()
    output_dir = Path(output_dir)
    if output_dir.is_symlink():
        raise ValueError('Mega 53 output directory must not be a symbolic link')
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.mega53-', dir=output_dir) as work:
        staged = []
        for name, value in entries.items():
            admit()
            source = Path(work) / name
            if isinstance(value, bytes):
                source.write_bytes(value)
            else:
                shutil.copyfile(value, source)
            staged.append((source, output_dir / name))
        published = []
        try:
            for source, target in staged:
                admit()
                os.link(source, target)
                published.append((source, target))
            admit()
            return [target for _, target in staged]
        except BaseException:
            for source, target in published:
                try:
                    current, original = target.lstat(), source.stat()
                    if (current.st_dev, current.st_ino) == (original.st_dev, original.st_ino):
                        target.unlink()
                except FileNotFoundError:
                    pass
            raise


def infer_drums(source, output_dir, targets, cancel_event=None):
    """AI kit-part separation using licensed Mega 53 weights, no DrumSep checkpoints."""
    return infer(source, output_dir, cancel_event=cancel_event, drum_targets=set(targets))


def dispatch_drums(source, output_dir, targets, *, remote=None, cancel_event=None):
    """Use the registered worker when supplied; never silently fall back locally."""
    targets = set(targets)
    names = {'drums': 'drums_without_percussions.wav', 'percussion': 'percussions.wav',
             'kick': 'kick.wav', 'snare': 'snare.wav', 'toms': 'toms.wav', 'hh': 'hh.wav'}
    if not targets or not targets <= names.keys():
        raise ValueError('Unsupported Mega 53 drum targets')
    if remote is None:
        return infer_drums(source, output_dir, targets, cancel_event=cancel_event), None
    if cancel_event is not None and cancel_event.is_set():
        raise RuntimeError('Separazione annullata')
    requested = sorted('hi-hat' if value == 'hh' else value for value in targets)
    result, worker_job_id = remote('drumsep', source, {'model': 'mvsep-mega53', 'targets': requested})
    audio = result.get('audio') if isinstance(result, dict) else None
    expected = {names[value] for value in targets}
    if not isinstance(audio, dict) or set(audio) != expected:
        raise ValueError('Il worker Mega 53 ha restituito stem mancanti o inattesi')
    from .ai_worker_artifacts import _verify_wav_bytes
    for payload in audio.values():
        if not isinstance(payload, bytes):
            raise ValueError('Il worker Mega 53 ha restituito dati audio non validi')
        _verify_wav_bytes(payload)
    if cancel_event is not None and cancel_event.is_set():
        raise RuntimeError('Separazione annullata')
    paths = _publish_outputs({name: audio[name] for name in sorted(expected)}, output_dir, cancel_event)
    return paths, worker_job_id


def infer_drums_vs_percussion(source, output_dir, cancel_event=None):
    """Extract the two native Mega 53 classes from the ORIGINAL MIX.

    This is not a complementary-mask split: the model's sources can overlap,
    so do not claim that their sum reconstructs the input.
    """
    paths = infer(source, output_dir, cancel_event=cancel_event,
                  drum_targets={'drums', 'percussion'})
    by_name = {Path(p).name: Path(p) for p in paths}
    if set(by_name) != {'drums_without_percussions.wav', 'percussions.wav'}:
        raise RuntimeError('Mega 53 did not produce both drums and percussion stems')
    return by_name['drums_without_percussions.wav'], by_name['percussions.wav']
