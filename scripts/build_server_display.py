"""Build a hash-pinned private Xvfb for target server packages, never at startup.

EL10 removed the distribution Xvfb package. Build against the target system's
libraries rather than requiring an unavailable RPM or enabling a third-party repo.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile

VERSION='21.1.24'
URL=f'https://xorg.freedesktop.org/releases/individual/xserver/xorg-server-{VERSION}.tar.xz'
SHA256='1a4eb36ca65cc3b1b936566d677a9786e13c11cd5806e951ac55f3f5ce3984af'
SOURCE_ARCHIVE=Path(__file__).resolve().parents[1]/'native/server_display/vendor'/f'xorg-server-{VERSION}.tar.xz'


def build(destination,source_archive=None):
    destination=Path(destination).resolve();destination.mkdir(parents=True,exist_ok=True)
    # Source only, with its complete upstream licence notices. Packaging cannot
    # depend on external DNS availability inside Rocky's CI container.
    archive=Path(source_archive or os.environ.get('MTA_XSERVER_SOURCE_ARCHIVE') or SOURCE_ARCHIVE).resolve()
    if not archive.is_file():raise ValueError('Missing pinned X.Org source archive: '+str(archive))
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=SHA256:raise ValueError('X server source checksum mismatch')
    with tempfile.TemporaryDirectory(prefix='mta-display-build-') as temp:
        root=Path(temp)
        with tarfile.open(archive) as source:source.extractall(root,filter='data')
        source=root/f'xorg-server-{VERSION}';output=root/'build'
        # Build only the framebuffer X server. No privileged Xorg driver, login
        # manager, physical device access, remote desktop or VNC server is built.
        options=['-Dxorg=false','-Dxvfb=true','-Dxnest=false','-Dxephyr=false','-Dxwin=false','-Dxquartz=false','-Dglamor=false','-Dglx=true','-Dsha1=libcrypto','-Ddri1=false','-Ddri2=false','-Ddri3=false','-Ddrm=false','-Dudev=false','-Dudev_kms=false','-Dhal=false','-Dsystemd_logind=false','-Dlinux_acpi=false','-Dlinux_apm=false','-Dsuid_wrapper=false','-Ddocs=false','-Ddevel-docs=false','-Ddocs-pdf=false','-Dsecure-rpc=false','-Dxdmcp=false','-Dxselinux=false','-Dxkb_dir=/usr/share/X11/xkb','-Dxkb_bin_dir=/usr/bin','-Dlisten_tcp=false','-Ddefault_font_path=/usr/share/fonts/X11/misc,built-ins']
        env={**os.environ,'PATH':str(Path(sys.executable).parent)+os.pathsep+os.environ.get('PATH','')}
        subprocess.run([sys.executable,'-m','mesonbuild.mesonmain','setup',str(output),str(source),'--buildtype=release','--prefix=/usr',*options],check=True,env=env)
        subprocess.run([sys.executable,'-m','mesonbuild.mesonmain','compile','-C',str(output),'-j','2','Xvfb'],check=True,env=env)
        installed=root/'installed'
        # Meson installation strips its build-only RPATH before packaging.
        subprocess.run([sys.executable,'-m','mesonbuild.mesonmain','install','-C',str(output),'--no-rebuild','--destdir',str(installed)],check=True,env=env)
        binary=installed/'usr/bin/Xvfb'
        if not binary.is_file():raise ValueError('Private Xvfb was not produced')
        target=destination/'Xvfb';shutil.copy2(binary,target);target.chmod(0o755)
        shutil.copy2(source/'COPYING',destination/'XSERVER-COPYING')
        record={'version':VERSION,'source':URL,'source_sha256':SHA256,'binary_sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
        (destination/'display-build.json').write_text(json.dumps(record,indent=2)+'\n')
        return target


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--source-archive',type=Path)
    args=parser.parse_args()
    print(build(args.output,args.source_archive))
