"""Pinned official UVR Karaoke 2 identity. Hash does not confer license rights."""
import hashlib
from pathlib import Path

UVR_KARA_2_SHA256 = "bf32e15105a09c0f7dddd2b67346146334d6f3ecb399ed7638eba2ab07cbf5f4"

def verify_kara_2(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing or unsafe UVR KARA 2 checkpoint")
    digest = hashlib.file_digest(path.open("rb"), "sha256").hexdigest()
    if digest != UVR_KARA_2_SHA256:
        raise ValueError("UVR KARA 2 checkpoint SHA-256 does not match pinned public release")
    return digest


def ensure_kara_2(path, download_into):
    """Restore the pinned checkpoint using a caller-authorized vendor download.

    The caller must pass the license admission gate before invoking this helper.
    Existing valid data is never downloaded twice; invalid data is never executed.
    """
    import os
    import tempfile
    path = Path(path)
    if path.is_symlink():
        raise ValueError("Refusing to replace symlink checkpoint")
    if path.exists():
        try:
            return verify_kara_2(path)
        except ValueError:
            pass
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.uvr-kara2-', dir=path.parent) as tmp:
        staging = Path(tmp) / path.name
        download_into(Path(tmp))
        digest = verify_kara_2(staging)
        if path.is_symlink():
            raise ValueError('Refusing to replace symlink checkpoint')
        os.replace(staging, path)
        return digest
