"""Exercise deletion only in isolated temporary directories."""
import importlib.util
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


@pytest.fixture
def gc(tmp_path):
    spec = importlib.util.spec_from_file_location('ai_gc', ROOT/'scripts/install_ai_engines.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    base = tmp_path/'mta';base.mkdir()
    proc = tmp_path/'proc';(proc/'self').mkdir(parents=True)
    (proc/'self/mountinfo').write_text('1 0 0:1 / / rw - rootfs rootfs rw\n')
    config = tmp_path/'env';config.write_text('')
    pending = tmp_path/'pending'
    def runtime(i, age=90000):
        p = base/('ai-'+format(i,'016x'));p.mkdir()
        (p/'sam').mkdir();(p/'sam/data').write_text('runtime')
        os.utime(p,(200000-age,200000-age))
        return p
    def cleanup(**kwargs):
        return m.cleanup_runtimes(base, config, proc=proc, now=200000, checkpoint=pending, **kwargs)
    return m,base,proc,config,pending,runtime,cleanup


def test_removes_only_old_unreferenced_runtime(gc):
    m,b,p,c,k,make,clean = gc
    old=make(1);young=make(2,age=100);active=make(3)
    c.write_text('MTA_SAM_AUDIO_PYTHON="'+str(active)+'/sam/bin/python"\n')
    other=b/'models';other.mkdir()
    result=clean()
    assert result['removed']==[old.name]
    assert not old.exists() and young.exists() and active.exists() and other.exists()


def test_dry_run_and_checkpoint_never_delete(gc):
    m,b,p,c,k,make,clean=gc;old=make(1)
    assert clean(dry_run=True)['removed']==[old.name]
    assert old.exists()
    k.write_text('setup in progress')
    assert 'deferred' in clean() and old.exists()


@pytest.mark.parametrize('source',['cmdline','environ','maps','exe','cwd','fd'])
def test_preserves_runtime_referenced_by_process(gc,source):
    m,b,p,c,k,make,clean=gc;old=make(1)
    pid=p/'123';pid.mkdir();(pid/'fd').mkdir()
    for name in ('cmdline','environ','maps'):(pid/name).write_bytes(b'')
    for name in ('exe','cwd'):(pid/name).symlink_to('/usr/bin/python')
    ref=str(old)+'/sam/bin/python'
    if source in ('cmdline','environ','maps'):(pid/source).write_bytes(('X='+ref+'\x00').encode())
    elif source=='fd':(pid/'fd/8').symlink_to(ref)
    else:
        (pid/source).unlink();(pid/source).symlink_to(ref)
    assert clean()['removed']==[] and old.exists()


def test_unreadable_processes_defer_cleanup(gc,monkeypatch):
    m,b,p,c,k,make,clean=gc;old=make(1)
    def denied(*args):raise PermissionError('proc not readable')
    monkeypatch.setattr(m,'process_runtime_references',denied)
    assert 'deferred' in clean() and old.exists()


def test_bind_mount_inside_runtime_is_preserved(gc):
    m,b,p,c,k,make,clean=gc;old=make(1)
    (p/'self/mountinfo').write_text('1 0 0:1 / '+str(old)+'/sam rw - ext4 /dev/a rw\n')
    assert clean()['removed']==[] and old.exists()


def test_symlink_and_foreign_directory_are_preserved(gc,tmp_path):
    m,b,p,c,k,make,clean=gc
    outside=tmp_path/'outside';outside.mkdir();(outside/'keep').write_text('keep')
    (b/('ai-'+'a'*16)).symlink_to(outside,target_is_directory=True)
    old=make(1);old.chmod(0o777)
    assert clean()['removed']==[] and (outside/'keep').exists() and old.exists()


def test_nested_symlink_is_not_followed(gc,tmp_path):
    m,b,p,c,k,make,clean=gc;old=make(1)
    outside=tmp_path/'outside';outside.mkdir();(outside/'keep').write_text('keep')
    (old/'sam/link').symlink_to(outside,target_is_directory=True)
    os.utime(old,(1,1))
    assert clean()['removed']==[old.name]
    assert (outside/'keep').exists()


def test_cleanup_only_after_successful_setup():
    native=(ROOT/'scripts/install_mta_native_wizard.sh').read_text()
    assert native.index('--cleanup')>native.index('rm -f "$checkpoint"')>native.index('systemctl is-active --quiet mta-server.service')
    legacy=(ROOT/'scripts/install_mta.sh').read_text()
    assert legacy.index('--cleanup')>legacy.index('MTA web health check failed')
