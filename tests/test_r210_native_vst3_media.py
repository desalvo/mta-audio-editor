"""Native VST3 API security and Windows-safe real media publication.

The YouTube network provider is a local WAV fixture. Media probing, file
publication, journals, rollback and persisted-project loading are real.
"""
# ruff: noqa: F811
import errno
import io
import os
from pathlib import Path
import stat
import threading
import time
import types

import pytest
from fastapi.testclient import TestClient
from app import main,auth,optional_plugins as plugins,fs_durability
from test_r210_media_stems_cleanup import project as media_project,youtube,run_youtube  # noqa: F401


@pytest.fixture
def native(tmp_path,monkeypatch):
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',True)
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER','true')
    monkeypatch.setattr(auth,'DATA_ROOT',tmp_path/'account')
    monkeypatch.setenv('MTA_OPTIONAL_VST3_DIR',str(tmp_path/'vst3'))
    monkeypatch.setattr(plugins,'_LOCK',threading.Lock())
    monkeypatch.setattr(plugins,'_JOBS',{})
    return TestClient(main.app)


def test_native_plugin_catalog_license_install_poll_and_uninstall_guards(native,monkeypatch):
    base='/api/native/optional-vst3';headers={'X-MTA-Request':'1'}
    response=native.get(base);assert response.status_code==200,response.text
    assert any(p['id']=='mverb' for p in response.json()['plugins'])
    blocked=native.get('/api/admin/optional-vst3')
    assert blocked.status_code==404 and blocked.json()['detail']=='Not available in native single-user mode'
    assert native.get(base+'/mverb/license').status_code==200
    body={'plugins':['mverb'],'accept_licenses':True}
    assert native.post(base+'/install',json=body).status_code==403
    assert native.post(base+'/install',json={**body,'accept_licenses':False},headers=headers).status_code==422
    assert native.post(base+'/install',json={**body,'plugins':['unknown']},headers=headers).status_code==422
    # Execute the real job manager with a simulated build, never download code
    # or claim a Windows plugin binary was compiled on this Linux runner.
    monkeypatch.setattr(plugins,'install_one',lambda spec,notify:{'id':spec['id'],'bundles':['MVerb.vst3']})
    accepted=native.post(base+'/install',json=body,headers=headers);assert accepted.status_code==200,accepted.text
    jid=accepted.json()['id'];deadline=time.monotonic()+5
    while time.monotonic()<deadline:
        result=native.get(base+'/jobs/'+jid).json()
        if result['state']!='running':break
        time.sleep(.01)
    assert result['state']=='completed' and result['plugins']['mverb']['state']=='installed'
    assert native.get(base+'/mverb/uninstall').status_code==200
    assert native.post(base+'/mverb/uninstall',json={'confirm':False,'remove_build_cache':True},headers=headers).status_code==422


def test_server_keeps_admin_role_and_native_alias_boundary(native,monkeypatch):
    monkeypatch.setattr(main,'NATIVE_SINGLE_USER',False)
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER','false')
    admin={'id':1,'role':'admin','language':'en','active':1}
    monkeypatch.setattr(main,'session_user',lambda request:admin)
    monkeypatch.setattr(auth,'session_user',lambda request:admin)
    assert native.get('/api/native/optional-vst3').status_code==404
    assert native.get('/api/admin/optional-vst3').status_code==200
    reader={'id':42,'role':'reader','language':'en','active':1}
    monkeypatch.setattr(main,'session_user',lambda request:reader)
    monkeypatch.setattr(auth,'session_user',lambda request:reader)
    assert native.get('/api/admin/optional-vst3').status_code==403
    monkeypatch.setattr(main,'session_user',lambda request:None)
    monkeypatch.setattr(auth,'session_user',lambda request:None)
    monkeypatch.setattr(main,'check_basic_auth',lambda request:False)
    assert native.get('/api/admin/optional-vst3').status_code==401


@pytest.fixture
def windows_directory_policy(monkeypatch):
    real_open=os.open;real_fsync=os.fsync;events={'file_flushes':0,'directory_opens':[]}
    def opened(path,*args,**kwargs):
        # Linux shutil uses directory descriptors for rmtree; Windows uses
        # its separate non-fd implementation. Keep that harness cleanup working.
        flags=args[0] if args else kwargs.get('flags',0)
        if not flags & getattr(os,'O_NONBLOCK',0) and not isinstance(path,int) and Path(path).is_dir():
            events['directory_opens'].append(str(path))
            raise PermissionError(errno.EACCES,'Windows refuses POSIX directory descriptors',str(path))
        return real_open(path,*args,**kwargs)
    def flushed(fd):
        if stat.S_ISREG(os.fstat(fd).st_mode):events['file_flushes']+=1
        return real_fsync(fd)
    # Avoid changing global os.name (which would select WindowsPath on Linux).
    monkeypatch.setattr(fs_durability,'os',types.SimpleNamespace(name='nt'))
    monkeypatch.setattr(os,'open',opened)
    monkeypatch.setattr(os,'fsync',flushed)
    return events


def test_windows_youtube_import_persists_real_audio_and_original(media_project,monkeypatch,windows_directory_policy):
    from app import storage
    youtube(monkeypatch);job=run_youtube(media_project)
    assert job['status']=='completed',job.get('error')
    reopened=storage.load_project(media_project.id)
    assert len(reopened.tracks)==1 and len(reopened.clip_library)==1
    audio=storage.audio_path(reopened.id,reopened.tracks[0].filename)
    assert audio.is_file() and main.ffprobe(audio)
    assert list(storage.originals_dir(reopened.id).iterdir())
    assert not list(storage.pdir(reopened.id).glob('.async-track-*.pending.json'))
    assert windows_directory_policy['file_flushes']>0
    assert not windows_directory_policy['directory_opens']


def test_windows_youtube_failure_reconciles_only_owned_files(media_project,monkeypatch,windows_directory_policy):
    from app import storage
    youtube(monkeypatch)
    existing=storage.original_path(media_project.id,'existing.bin');existing.write_bytes(b'keep')
    monkeypatch.setattr(main,'_normalize_audio_to_project_rate',lambda *a:(_ for _ in ()).throw(ValueError('conversion failed')))
    result=run_youtube(media_project);assert result['status']=='failed'
    assert existing.read_bytes()==b'keep'
    assert not list((storage.pdir(media_project.id)/'audio').iterdir())
    assert list(storage.originals_dir(media_project.id).iterdir())==[existing]
    assert not list(storage.pdir(media_project.id).glob('.async-track-*.pending.json'))
    assert not windows_directory_policy['directory_opens']


def test_windows_exclusive_copy_preserves_existing_files(tmp_path,windows_directory_policy):
    destination=tmp_path/'new.wav'
    main._copy_limited(io.BytesIO(b'audio'),destination)
    assert destination.read_bytes()==b'audio'
    with pytest.raises(FileExistsError):main._copy_limited(io.BytesIO(b'overwrite'),destination)
    assert destination.read_bytes()==b'audio'
    assert not windows_directory_policy['directory_opens']


@pytest.mark.skipif(os.name=='nt',reason='POSIX-specific mandatory directory flush contract')
def test_posix_directory_failure_still_fails_publication_and_closes_fd(tmp_path,monkeypatch):
    real_fsync=os.fsync;directory_fds=[]
    def fail(fd):
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            directory_fds.append(fd);raise OSError(errno.EIO,'injected directory flush failure')
        real_fsync(fd)
    monkeypatch.setattr(os,'fsync',fail)
    destination=tmp_path/'owned.wav'
    with pytest.raises(OSError,match='flush failure'):main._copy_limited(io.BytesIO(b'audio'),destination)
    assert not destination.exists() and directory_fds
    for fd in directory_fds:
        with pytest.raises(OSError):os.fstat(fd)


@pytest.mark.parametrize('locale',['en','it'])
def test_plugin_plain_text_error_is_readable_and_not_json_exception(locale,chromium_capability):
    api=pytest.importorskip('playwright.sync_api')
    with api.sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,args=['--no-sandbox'])
        page=browser.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        page.route('http://mta.test/',lambda r:r.fulfill(body='<body class="native-single-user"><div id="catalog"></div></body>',content_type='text/html'))
        page.route('**/api/native/optional-vst3',lambda r:r.fulfill(status=404,body='Not available in native single-user mode',content_type='text/plain'))
        page.goto('http://mta.test/');page.evaluate('(language)=>{window.MtaLocale={language}}',locale)
        page.add_script_tag(content=(Path(__file__).resolve().parents[1]/'app/static/optional_plugins.js').read_text())
        page.evaluate("async()=>{await openOptionalVst3(document.getElementById('catalog'))}")
        message=page.locator('#catalog').inner_text()
        assert ('Risposta inattesa del server' if locale=='it' else 'Unexpected server response') in message
        assert 'HTTP 404' in message and 'Not available' in message
        assert 'Unexpected token' not in message and not errors
        browser.close()
