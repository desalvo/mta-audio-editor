"""Fixed adapter identities for configurable inference entry points.

An executable flag, a label or an operator-supplied digest cannot prove which
checkpoint arbitrary code loads. Only the installed MTA integration for a kind
is admitted here. Its loader still owns checkpoint and current-policy checks.
This is not confinement against an administrator who can replace installed code.
"""
from pathlib import Path
import sys


UNIFIED_KINDS = frozenset({
    'whisper', 'chords-ml', 'demucs', 'drumsep', 'sam-audio',
    'singer-separation', 'backing-vocals', 'markers',
})
ACE_KINDS = frozenset({'ace-step', 'arranger', 'remix'})


def require_current_interpreter(value):
    """An operator override cannot introduce another executable/import context.

    The running installation is the trust root, not a digest supplied alongside
    an executable. Even another venv using the same binary changes imports.
    Managed runtime selection is separate and still requires loader review.
    """
    path = Path(value)
    if (getattr(sys, 'frozen', False) or not path.is_absolute()
            or str(path) != sys.executable or not path.is_file()):
        raise ValueError('Configured AI Python has no verified interpreter/import contract')
    return str(path)


def supported_worker(kind: str, worker: Path) -> bool:
    """Bind kind to a fixed integration; never trust a matching basename alone."""
    from .studio_catalog import KINDS
    root = Path(__file__).resolve().parent
    worker = Path(worker)
    try:
        if not worker.is_absolute() or worker.is_symlink() or not worker.is_file():
            return False
        # Parent symlinks and ../aliases must not disguise a copied adapter.
        if worker != worker.resolve(strict=True):
            return False
        if kind in UNIFIED_KINDS:
            return worker == root / 'ai_unified_adapter.py'
        if kind in KINDS:
            return worker == root / 'ai_studio_adapter.py'
        if kind in ACE_KINDS:
            if worker == root / 'ace_step_http_worker.py':
                return True
            # Native bundles copy their ACE adapter and its sibling imports into
            # a managed directory. Every shipped sibling must still match; an
            # unchanged entry script beside substituted code is insufficient.
            from .ace_step_desktop_manager import home, _ADAPTER_FILES
            directory = home() / 'adapter'
            if worker != directory / 'ace_step_http_worker.py':
                return False
            for name in _ADAPTER_FILES:
                target = directory / name
                source = root / name
                if (target.is_symlink() or not target.is_file()
                        or target.resolve(strict=True) != target
                        or target.stat().st_nlink != 1
                        or target.stat().st_size != source.stat().st_size
                        or target.read_bytes() != source.read_bytes()):
                    return False
            return True
    except (OSError, ValueError, RuntimeError):
        return False
    return False


def deny_opaque_executor():
    """No generic executable-to-checkpoint protocol is supported yet."""
    from .model_license_policy import LicenseDenied
    raise LicenseDenied('Configured executable has no verified checkpoint loader contract; use a supported MTA integration')
