"""Explicit, checksum-pinned GM bank installation for every desktop/server OS."""
import hashlib
import os
from pathlib import Path
import shutil
import tarfile
import tempfile

ARCHIVE_URL='https://deb.debian.org/debian/pool/main/f/fluid-soundfont/fluid-soundfont_3.1.orig.tar.gz'
ARCHIVE_BYTES=134835922
ARCHIVE_SHA='2621acaa1c78e4abdb24bdd163230cc577e61276936d6aa6e3180582142f0343'
BANK_SHA='74594e8f4250680adf590507a306655a299935343583256f3b722c48a1bc1cb0'
BANK_BYTES=148398306


def root():
    from .auth import data_root
    folder=data_root()/'soundfonts'
    if folder.is_symlink():raise ValueError('Unsafe soundbank directory')
    folder.mkdir(parents=True,exist_ok=True,mode=0o700)
    return folder


def _digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def self_test():
    """Produce actual note PCM; an import/library lookup is insufficient."""
    from .gm_instruments import Synth
    import numpy as np
    synth=Synth({'program':0,'reverb_level':0},48000)
    try:
        pcm=synth.process([(bytes([144,60,100]),.05)],duration=.1,sample_rate=48000)
        if pcm.shape!=(2,4800) or not np.isfinite(pcm).all() or abs(pcm[:,:2300]).max()>1e-6 or abs(pcm[:,2600:]).max()<.001:
            raise RuntimeError('GM instrument failed its scheduled-note audio test')
        return {'tested':True,'sample_rate':48000,'frames':4800,'peak':float(abs(pcm).max())}
    finally:synth.close()


def install(cancelled,progress,*,archive=None):
    from .ai_project_lock import project_publication_lock
    from .secure_https import https_urlopen
    from .storage import _atomic_json_write
    from .fs_durability import sync_directory
    with project_publication_lock('studio-model:gm'):
        folder=root();target=folder/'FluidR3_GM.sf2'
        if target.is_symlink():raise ValueError('Unsafe existing soundbank')
        if target.exists():
            if _digest(target)!=BANK_SHA:raise ValueError('Existing soundbank differs from the reviewed bank; inspect it before replacing')
            progress('testing',0,0);return self_test()
        with tempfile.TemporaryDirectory(prefix='.gm-install-',dir=folder) as raw:
            work=Path(raw);packed=work/'source.tar.gz'
            if archive is not None:
                # CLI/offline administrator input, never a path from a web request.
                shutil.copyfile(archive,packed)
            else:
                with https_urlopen(ARCHIVE_URL,timeout=90) as source,packed.open('xb') as output:
                    done=0
                    while chunk:=source.read(1024*1024):
                        if cancelled():raise RuntimeError('GM installation cancelled')
                        done+=len(chunk)
                        if done>ARCHIVE_BYTES:raise ValueError('GM download exceeds pinned size')
                        output.write(chunk);progress('downloading',done,ARCHIVE_BYTES)
                    output.flush();os.fsync(output.fileno())
            if packed.stat().st_size!=ARCHIVE_BYTES or _digest(packed)!=ARCHIVE_SHA:raise ValueError('GM source archive failed checksum verification')
            progress('verifying',0,0)
            with tarfile.open(packed,'r:gz') as bundle:
                for basename,limit in [('FluidR3_GM.sf2',BANK_BYTES),('COPYING',32768),('README',32768)]:
                    if cancelled():raise RuntimeError('GM installation cancelled')
                    member=bundle.getmember('fluid-soundfont-3.1/'+basename)
                    if not member.isfile() or member.size>limit:raise ValueError('Unsafe GM archive member')
                    with bundle.extractfile(member) as inp,(work/basename).open('xb') as output:
                        shutil.copyfileobj(inp,output);output.flush();os.fsync(output.fileno())
            if _digest(work/'FluidR3_GM.sf2')!=BANK_SHA:raise ValueError('GM soundbank integrity mismatch')
            if cancelled():raise RuntimeError('GM installation cancelled before publication')
            progress('installing',0,0)
            for name in ('COPYING','README'):os.replace(work/name,folder/('FluidR3-'+name+'.txt'))
            os.replace(work/'FluidR3_GM.sf2',target);sync_directory(folder)
            try:
                progress('testing',0,0);result=self_test()
                if cancelled():raise RuntimeError('GM installation cancelled before activation')
                _atomic_json_write(folder/'gm-installation.json',{'version':'3.1','bank_sha256':BANK_SHA,'license':'MIT',**result})
            except BaseException:
                # The only newly published owned bank; do not touch system banks.
                target.unlink(missing_ok=True);raise
            return result


def uninstall():
    from .ai_project_lock import project_publication_lock
    from .vst3_live import SESSIONS,SESSION_LOCK
    with project_publication_lock('studio-model:gm'),SESSION_LOCK:
        if any(not s.closed and any(t.instrument and t.instrument.plugin=='gm_soundfont' for t in s.project.tracks) for s in SESSIONS):
            raise ValueError('Stop GM playback/monitoring before uninstalling the soundbank')
        folder=root();bank=folder/'FluidR3_GM.sf2'
        if bank.is_symlink() or (bank.is_file() and _digest(bank)!=BANK_SHA):raise ValueError('Refusing to remove an unrecognized soundbank')
        for name in ('FluidR3_GM.sf2','gm-installation.json','FluidR3-COPYING.txt','FluidR3-README.txt'):
            path=folder/name
            if path.is_symlink():raise ValueError('Unsafe managed soundbank path')
        for name in ('FluidR3_GM.sf2','gm-installation.json','FluidR3-COPYING.txt','FluidR3-README.txt'):(folder/name).unlink(missing_ok=True)
        return {'removed':True,'project_midi_preserved':True}
