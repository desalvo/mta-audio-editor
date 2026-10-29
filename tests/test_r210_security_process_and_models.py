"""Synthetic model bytes and real local processes; no downloads or model inference."""
import io
import os
from pathlib import Path
import signal
import sys
import threading
import time
import zipfile

import pytest

from app import chord_ml,separator_process


def archive(items):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as z:
        for key,value in items:z.writestr(key,value)
    return out.getvalue()


@pytest.mark.parametrize('name',['../escape','/absolute','C:/escape','a\\b','a//b','a/./b','a/../b','x.','x ','CON','a/aux.txt','a/COM1.txt'])
def test_untrusted_model_names_fail_before_any_extraction(tmp_path,name):
    dest=tmp_path/'out'
    with zipfile.ZipFile(io.BytesIO(archive([('safe.txt',b'safe'),(name,b'evil')]))) as z:
        with pytest.raises(RuntimeError):chord_ml._safe_extract(z,dest)
    assert not dest.exists()


@pytest.mark.parametrize('names',[['same','SAME'],['node','node/child'],['a/','A/']])
def test_alias_and_file_directory_conflicts_fail_before_writes(tmp_path,names):
    with zipfile.ZipFile(io.BytesIO(archive([(n,b'x') for n in names]))) as z:
        with pytest.raises(RuntimeError):chord_ml._safe_extract(z,tmp_path/'out')
    assert not (tmp_path/'out').exists()


@pytest.mark.parametrize('mode',[0o120777,0o020600,0o010600])
def test_links_and_special_archive_entries_are_rejected(tmp_path,mode):
    item=zipfile.ZipInfo('link');item.create_system=3;item.external_attr=mode<<16
    with zipfile.ZipFile(io.BytesIO(archive([(item,b'target')]))) as z:
        with pytest.raises(RuntimeError):chord_ml._safe_extract(z,tmp_path/'out')


@pytest.mark.parametrize('limit',['MAX_DOWNLOAD_BYTES','MAX_EXPANDED_BYTES','MAX_ARCHIVE_MEMBERS'])
def test_expanded_archive_budgets_preflight_all_members(tmp_path,monkeypatch,limit):
    monkeypatch.setattr(chord_ml,limit,1)
    with zipfile.ZipFile(io.BytesIO(archive([('a',b'ab'),('b',b'cd')]))) as z:
        with pytest.raises(RuntimeError):chord_ml._safe_extract(z,tmp_path/'out')
    assert not (tmp_path/'out').exists()


def test_extraction_does_not_overwrite_existing_or_follow_destination_link(tmp_path):
    occupied=tmp_path/'occupied';occupied.mkdir();(occupied/'keep').write_bytes(b'original')
    for dest in (occupied,tmp_path/'link'):
        if dest.name=='link':dest.symlink_to(occupied,target_is_directory=True)
        with zipfile.ZipFile(io.BytesIO(archive([('keep',b'attack')]))) as z:
            with pytest.raises(RuntimeError):chord_ml._safe_extract(z,dest)
    assert (occupied/'keep').read_bytes()==b'original'


def test_model_download_budget_removes_only_own_partial_file(tmp_path,monkeypatch):
    class Response(io.BytesIO):pass
    monkeypatch.setattr(chord_ml,'https_urlopen',lambda *a,**kw:Response(b'123456'))
    monkeypatch.setattr(chord_ml,'MAX_DOWNLOAD_BYTES',3)
    dest=tmp_path/'model.zip'
    with pytest.raises(RuntimeError,match='size limit'):chord_ml._download_zip('https://models.test/archive.zip',dest)
    assert not dest.exists()
    dest.write_bytes(b'keep')
    with pytest.raises(FileExistsError):chord_ml._download_zip('https://models.test/archive.zip',dest)
    assert dest.read_bytes()==b'keep'


def test_failed_secondary_download_never_publishes_partial_model(tmp_path,monkeypatch):
    monkeypatch.setenv('MTA_CHORD_ML_MODEL_DIR',str(tmp_path/'models'))
    monkeypatch.setattr('app.model_license_policy.evaluate_model',lambda *a:None)
    def download(url,dest):
        if url==chord_ml.BTC_BODY_ARCHIVE:raise RuntimeError('secondary unavailable')
        dest.write_bytes(archive([('repo/btc_hcqt_beatlesft.pt',b'weights')]))
    monkeypatch.setattr(chord_ml,'_download_zip',download)
    with pytest.raises(RuntimeError,match='secondary'):chord_ml.download_model('btc-hcqt')
    assert not chord_ml.model_dir('btc-hcqt').exists()
    assert not list((tmp_path/'models').glob('.chord-install-*'))


def test_existing_install_is_preserved_without_redownload(tmp_path,monkeypatch):
    monkeypatch.setenv('MTA_CHORD_ML_MODEL_DIR',str(tmp_path/'models'))
    monkeypatch.setattr('app.model_license_policy.evaluate_model',lambda *a:None)
    root=chord_ml.model_dir('btc-hcqt');root.mkdir(parents=True);(root/'keep').write_bytes(b'original')
    monkeypatch.setattr(chord_ml,'_download_zip',lambda *a:pytest.fail('must not redownload or replace installed model'))
    with pytest.raises(ValueError,match='existing'):chord_ml.download_model('btc-hcqt')
    assert (root/'keep').read_bytes()==b'original'


def test_revoked_rights_at_publication_preserve_absent_install(tmp_path,monkeypatch):
    monkeypatch.setenv('MTA_CHORD_ML_MODEL_DIR',str(tmp_path/'models'));calls=[]
    def evaluate(*args):
        calls.append(args)
        if len(calls)==2:raise ValueError('rights revoked')
    monkeypatch.setattr('app.model_license_policy.evaluate_model',evaluate)
    monkeypatch.setattr(chord_ml,'_download_zip',lambda url,dest:dest.write_bytes(archive([(f'repo/cache_data/{i}.sdict',b'x') for i in range(5)])))
    with pytest.raises(ValueError,match='revoked'):chord_ml.download_model('chordformer')
    assert not chord_ml.model_dir('chordformer').exists()


@pytest.mark.parametrize('name',['../outside','missing','/outside'])
def test_delete_and_lookup_require_exact_registered_model(tmp_path,monkeypatch,name):
    monkeypatch.setenv('MTA_CHORD_ML_MODEL_DIR',str(tmp_path/'models'))
    with pytest.raises(ValueError):chord_ml.delete_model(name)
    with pytest.raises(ValueError):chord_ml.model_dir(name)


def test_actual_custom_separator_no_longer_deadlocks_on_pipe_sized_output(tmp_path,monkeypatch):
    from app import main
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',True);monkeypatch.setattr('app.native_ai_routing.is_remote',lambda kind:False)
    script=tmp_path/'separator.py'
    script.write_text("import sys\nfrom pathlib import Path\nsys.stdout.write('x'*2_000_000)\nPath(sys.argv[sys.argv.index('--lead')+1]).write_bytes(b'lead')\nPath(sys.argv[sys.argv.index('--backing')+1]).write_bytes(b'backing')\n")
    source=tmp_path/'source with spaces;not-shell.wav';source.write_bytes(b'input')
    lead,backing=tmp_path/'lead.wav',tmp_path/'backing.wav'
    # The bounded process primitive remains an operator/internal tool. The
    # application no longer treats an opaque command as a licensed model.
    started=time.monotonic()
    separator_process.run([sys.executable,str(script),'--input',str(source),'--lead',str(lead),'--backing',str(backing)])
    assert time.monotonic()-started<10 and lead.read_bytes()==b'lead' and backing.read_bytes()==b'backing'


def test_separator_cancellation_before_start_never_spawns(monkeypatch):
    event=threading.Event();event.set()
    monkeypatch.setattr(separator_process.subprocess,'Popen',lambda *a,**kw:pytest.fail('spawned cancelled request'))
    with pytest.raises(RuntimeError,match='cancelled'):separator_process.run([sys.executable],cancel_event=event)


def test_separator_log_overflow_and_failure_are_explicit():
    with pytest.raises(RuntimeError,match='output limit'):
        separator_process.run([sys.executable,'-c',"import sys;sys.stdout.write('x'*100000)"],max_log_bytes=1024)
    with pytest.raises(RuntimeError,match='final diagnostic'):
        separator_process.run([sys.executable,'-c',"import sys;sys.stderr.write('x'*5000+'final diagnostic');sys.exit(2)"])


@pytest.mark.skipif(os.name!='posix',reason='POSIX process-group fixture; native Windows acceptance separate')
def test_separator_timeout_stops_its_owned_process(tmp_path):
    pidfile=tmp_path/'pid'
    code="import os,time;from pathlib import Path;Path("+repr(str(pidfile))+").write_text(os.read(os.open('/proc/self/stat',os.O_RDONLY),100).split()[0].decode());time.sleep(30)"
    with pytest.raises(RuntimeError,match='timed out'):separator_process.run([sys.executable,'-c',code],timeout=.3)
    pid=int(pidfile.read_text())
    assert not (Path('/proc')/str(pid)).exists()


@pytest.mark.skipif(os.name!='posix',reason='POSIX process-group fixture; escaped workers remain separate')
def test_separator_cancel_stops_worker_and_normal_descendant(tmp_path):
    pidfile=tmp_path/'child';event=threading.Event()
    child="import os,time;from pathlib import Path;fd=os.open('/proc/self/stat',os.O_RDONLY);kernel=os.read(fd,100).split()[0].decode();os.close(fd);Path("+repr(str(pidfile))+").write_text(kernel+','+str(os.getpid()));time.sleep(30)"
    code="import subprocess,sys,time;subprocess.Popen([sys.executable,'-c',"+repr(child)+"]);time.sleep(30)"
    def cancel():
        deadline=time.monotonic()+5
        while not pidfile.exists() and time.monotonic()<deadline:time.sleep(.01)
        event.set()
    thread=threading.Thread(target=cancel,daemon=True);thread.start()
    try:
        with pytest.raises(RuntimeError,match='cancelled'):separator_process.run([sys.executable,'-c',code],cancel_event=event,timeout=10)
        kernel_pid,_=map(int,pidfile.read_text().split(','));path=Path('/proc')/str(kernel_pid)/'stat'
        assert not path.exists() or path.read_text().split(') ',1)[1].startswith('Z')
    finally:
        thread.join(1)
        if pidfile.exists():
            try:os.kill(int(pidfile.read_text().split(',')[1]),signal.SIGKILL)
            except ProcessLookupError:pass


def test_failed_member_crc_never_publishes_an_installed_model(tmp_path,monkeypatch):
    monkeypatch.setenv('MTA_CHORD_ML_MODEL_DIR',str(tmp_path/'models'))
    monkeypatch.setattr('app.model_license_policy.evaluate_model',lambda *a:None)
    data=archive([(f'repo/cache_data/{i}.sdict',b'unique-weights-'+str(i).encode()) for i in range(5)])
    position=data.index(b'unique-weights-4');data=data[:position]+b'X'+data[position+1:]
    monkeypatch.setattr(chord_ml,'_download_zip',lambda url,dest:dest.write_bytes(data))
    with pytest.raises(zipfile.BadZipFile):chord_ml.download_model('chordformer')
    assert not chord_ml.model_dir('chordformer').exists()
    assert not list((tmp_path/'models').glob('.chord-install-*'))
