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


def configured():
    return bool(os.getenv('MTA_MEGA53_ROOT') and os.getenv('MTA_MEGA53_CONFIG') and os.getenv('MTA_MEGA53_CHECKPOINT'))


def infer(source, output_dir, cancel_event=None, drum_targets=None):
    """Return canonical (lead, backing) WAVs; fail closed on ambiguous outputs."""
    from .model_license_policy import evaluate_model
    evaluate_model('mvsep-mega53')
    root = _verified_directory(os.getenv('MTA_MEGA53_ROOT', ''))
    config = _verified_file(os.getenv('MTA_MEGA53_CONFIG', ''), 'config')
    checkpoint = verify_mega53_checkpoint(os.getenv('MTA_MEGA53_CHECKPOINT', ''))
    python = _verified_file(os.getenv('MTA_MEGA53_PYTHON', sys.executable), 'Python interpreter')
    source = _verified_file(str(source), 'source audio')
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='mta-mega53-') as work:
        work = Path(work)
        inputs, outputs = work / 'inputs', work / 'outputs'
        inputs.mkdir(); outputs.mkdir()
        shutil.copyfile(source, inputs / ('mta_input' + source.suffix))
        cmd = [str(python), str(root / 'inference.py'), '--model_type', 'bs_roformer',
               '--config_path', str(config), '--start_check_point', str(checkpoint),
               '--input_folder', str(inputs), '--store_dir', str(outputs)]
        from .separator_process import run
        try:run(cmd,cwd=root,cancel_event=cancel_event)
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
            results = []
            for name in sorted(drum_targets):
                if len(stems[name]) != 1:
                    raise RuntimeError(f'Mega 53 drum output missing or ambiguous: {name}')
                dest = out / ({'percussion': 'percussions', 'drums': 'drums_without_percussions'}.get(name, name) + '.wav')
                shutil.copyfile(stems[name][0], dest)
                results.append(dest)
            return results
        if any(len(stems[name]) != 1 for name in ('lead-vocal', 'back-vocal')):
            raise RuntimeError('Mega 53 outputs missing or ambiguous: lead-vocal and back-vocal required')
        lead, backing = out / 'lead_vocals.wav', out / 'backing_vocals.wav'
        shutil.copyfile(stems['lead-vocal'][0], lead)
        shutil.copyfile(stems['back-vocal'][0], backing)
        return lead, backing, 'mvsep-mega53'


def infer_drums(source, output_dir, targets, cancel_event=None):
    """AI kit-part separation using licensed Mega 53 weights, no DrumSep checkpoints."""
    return infer(source, output_dir, cancel_event=cancel_event, drum_targets=set(targets))


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
