"""Live processing through a compiled callback and persistent native plugins."""
import os
from pathlib import Path
import time
import numpy as np
import pytest
import soundfile as sf
from app import cpp_audio
from app.models import Project,Track,Clip,InsertPlugin
from test_r210_cpp_audio_engine import compiled_core  # noqa: F401


@pytest.fixture
def live(request,tmp_path,monkeypatch):
    binary=request.getfixturevalue('compiled_core');monkeypatch.setenv('MTA_AUDIO_CORE_PATH',str(binary));cpp_audio._load.cache_clear()
    source=tmp_path/'dry.wav';sf.write(source,np.full((48000,2),.1,dtype=np.float32),48000,subtype='FLOAT')
    track=Track(id='t',name='Track',filename='dry.wav',duration_ms=1000,channels=2,clips=[Clip(id='c',source_end_ms=1000)])
    return Project(id='p',title='Live',sample_rate=48000,tracks=[track]),source


def test_stream_device_consumes_blocks_and_finishes_without_python_callback(live):
    from app.native_transport import StreamDevice
    _,_=live
    with StreamDevice(48000,1024,_test_null=True) as d:
        assert d.push(np.full((512,2),.2,dtype=np.float32));assert d.buffered()==512
        with pytest.raises(RuntimeError):d.push(np.full((512,2),np.nan,dtype=np.float32))
        assert d.push(np.full((512,2),.4,dtype=np.float32));d.finish();d.control('play')
        deadline=time.monotonic()+2
        while not d.status()['ended'] and time.monotonic()<deadline:time.sleep(.01)
        assert d.status()['ended'] and d.status()['position']==1024 and not d.status()['physical']
        d.control('pause');d.control('seek',0);assert d.buffered()==0


def test_live_graph_builtin_order_fader_bypass_and_tail(live):
    pytest.importorskip('av')
    from app.vst3_live_graph import Graph
    p,f=live;p.tracks[0].inserts=[InsertPlugin(id='a',plugin='amplify',preset='plus-6db')];p.master_volume_db=-6
    with_graph=Graph(p,[f],tail_seconds=.02)
    try:
        np.testing.assert_allclose(with_graph.read(),.1,atol=1e-6)
        p2=p.model_copy(deep=True);p2.tracks[0].volume_db=-6
        assert with_graph.update(p2)
        np.testing.assert_allclose(with_graph.read(),.1*10**(-6/20),atol=1e-6)
        while len(with_graph.read()):pass
    finally:with_graph.close()
    p.tracks[0].master_bypass=True;p.tracks[0].volume_db=0
    g=Graph(p,[f],start_frame=12000,tail_seconds=0)
    try:assert g.position==12000;np.testing.assert_allclose(g.read(),.1*10**(6/20),atol=1e-6)
    finally:g.close()


def test_all_builtin_presets_can_enter_live_filter_graph():
    pytest.importorskip('av')
    from app.plugins import PRESETS,plugin_filter
    from app.vst3_live_graph import Filter
    for name,presets in PRESETS.items():
        for preset in presets:
            expr=plugin_filter(InsertPlugin(id='test',plugin=name,preset=preset))
            if expr:
                node=Filter(expr,48000,2);node.process(np.zeros((512,2),np.float32));node.flush()


@pytest.fixture
def real_plugin(monkeypatch):
    pytest.importorskip('pedalboard');pytest.importorskip('av')
    path=os.getenv('MTA_TEST_LIVE_VST3')
    if not path:pytest.skip('Set MTA_TEST_LIVE_VST3 to an independently installed audio effect')
    path=Path(path);assert path.exists();monkeypatch.setenv('MTA_VST3_PATHS',str(path.parent));return path


def test_real_vst_persistent_instance_state_and_live_parameter_change(live,real_plugin):
    from app.vst3_live_graph import Graph
    p,f=live;p.tracks[0].inserts=[InsertPlugin(id='v',plugin='vst3',params={'path':str(real_plugin)})]
    g=Graph(p,[f],tail_seconds=0)
    try:
        node=g.plugins[('t','v')];identity=id(node.plugin);first=g.read();assert first.shape==(512,2) and np.isfinite(first).all()
        values=node.values();assert values['__mta_state_b64']
        key=next(k for k in values if k not in ('path','__mta_state_b64'))
        newer=p.model_copy(deep=True);newer.tracks[0].inserts[0].params[key]=.25
        assert g.update(newer);assert id(g.plugins[('t','v')].plugin)==identity
        assert abs(node.plugin.parameters[key].raw_value-.25)<1e-6
        assert np.isfinite(g.read()).all()
    finally:g.close()


def test_real_live_worker_pause_seek_update_shutdown(live,real_plugin):
    from app.vst3_live import Session
    p,f=live;p.master_inserts=[InsertPlugin(id='v',plugin='vst3',params={'path':str(real_plugin)})]
    s=Session(p,[f],0,_test_null=True)
    try:
        assert s.status()['live_vst3'] and s.status()['plugin_count']==1
        time.sleep(.05);a=s.control('pause');assert a['position']>0
        pos=a['position'];time.sleep(.05);assert s.status()['position']==pos
        s.control('seek',500);assert s.status()['position']==24000
        p.master_volume_db=-6;s.update(p);s.control('play');time.sleep(.06)
        assert s.status()['position']>24000 and not s.status()['failed']
    finally:s.close()
    assert s.proc.poll() is not None


def test_bad_command_does_not_terminate_healthy_worker(live,real_plugin):
    from app.vst3_live import Session
    p,f=live;s=Session(p,[f],0,_test_null=True)
    try:
        with pytest.raises(RuntimeError):s.request('unsupported',timeout=1)
        # Fresh status remains usable after a rejected command.
        assert not s.status()['failed']
    finally:s.close()


def test_stalled_live_worker_has_bounded_shutdown(live):
    import signal
    if not hasattr(signal,'SIGSTOP'):pytest.skip('POSIX process stop is required for this fault injection')
    pytest.importorskip('pedalboard');pytest.importorskip('av')
    from app.vst3_live import Session
    p,f=live;s=Session(p,[f],0,_test_null=True)
    try:
        os.kill(s.proc.pid,signal.SIGSTOP)
        started=time.monotonic()
        with pytest.raises(RuntimeError,match='timed out'):s.request('pause',timeout=.1)
        s.close();assert time.monotonic()-started<4
        assert s.proc.poll() is not None
    finally:s.close()


def test_real_master_state_snapshot_and_headless_editor_failure(live,real_plugin):
    from app.vst3_live import Session
    p,f=live;p.master_inserts=[InsertPlugin(id='masterv',plugin='vst3',params={'path':str(real_plugin)})]
    s=Session(p,[f],0,_test_null=True)
    try:
        s.edited=True;states=s.states();assert states[0]['route']=='master' and states[0]['params']['__mta_state_b64']
        key=next(k for k in states[0]['params'] if k not in ('path','__mta_state_b64'))
        p.master_inserts[0].params[key]=.35;s.update(p)
        assert abs(s.states()[0]['params'][key]-.35)<1e-6
        if not os.environ.get('DISPLAY') and not os.environ.get('WAYLAND_DISPLAY') and os.name!='nt' and __import__('sys').platform!='darwin':
            token=s.editor('master','masterv')['editor_id'];deadline=time.monotonic()+3
            while time.monotonic()<deadline:
                try:result=s.editor_poll(token)
                except RuntimeError:break
                if result['state']!='running':break
                time.sleep(.02)
            else:pytest.fail('Headless editor did not finish')
            assert not s.status()['failed']
    finally:s.close()


def test_mixed_vst_builtin_order_and_latency_alignment(live,monkeypatch,tmp_path):
    pytest.importorskip('av');pedalboard=pytest.importorskip('pedalboard')
    from app.vst3_live_graph import Graph
    root=tmp_path/'Square.vst3';root.mkdir();monkeypatch.setenv('MTA_VST3_PATHS',str(tmp_path))
    class BufferedSquare:
        is_instrument=False
        parameters={}
        raw_state=b'state'
        def __init__(self):self.pending=None
        def process(self,data,*args,**kwargs):
            old=self.pending;self.pending=data*data
            return old if old is not None else np.empty((2,0),np.float32)
    monkeypatch.setattr(pedalboard,'load_plugin',lambda _:BufferedSquare())
    p,f=live;p.tracks[0].inserts=[InsertPlugin(id='pre',plugin='amplify',preset='plus-6db'),InsertPlugin(id='square',plugin='vst3',params={'path':str(root)}),InsertPlugin(id='post',plugin='amplify',preset='minus-6db')]
    second=p.tracks[0].model_copy(deep=True);second.id='dry';second.inserts=[];p.tracks.append(second)
    g=Graph(p,[f,f],tail_seconds=0)
    try:np.testing.assert_allclose(g.read(),.1+(.1*10**(6/20))**2*10**(-6/20),atol=1e-6)
    finally:g.close()


def test_stop_saves_live_editor_state_before_releasing_session(live,monkeypatch):
    from app import native_transport as nt,storage
    p,f=live;p.tracks[0].inserts=[InsertPlugin(id='v',plugin='vst3',params={'path':'/Example.vst3'})]
    events=[]
    class Worker:
        def states(self):events.append('snapshot');return [{'route':'t','insert':'v','params':{'path':'/Example.vst3','gain':.8}}]
        def close(self):events.append('close')
    monkeypatch.setattr(storage,'load_project',lambda pid:p)
    def save(project,**kw):events.append('save');assert project.tracks[0].inserts[0].params['gain']==.8
    monkeypatch.setattr(storage,'save_project',save)
    monkeypatch.setattr(nt,'_DEVICE',Worker());monkeypatch.setattr(nt,'_PROJECT','p')
    result=nt.stop();assert events==['snapshot','save','close'] and result['states'][0]['params']['gain']==.8
    assert nt._DEVICE is None


def test_original_editor_controls_same_live_instance_while_audio_runs(live,real_plugin):
    if not os.environ.get('DISPLAY') and not os.environ.get('MTA_TEST_NATIVE_GUI'):pytest.skip('Requires a graphical display (CI uses Xvfb)')
    from app.vst3_live import Session
    p,f=live;p.tracks[0].inserts=[InsertPlugin(id='v',plugin='vst3',params={'path':str(real_plugin)})]
    s=Session(p,[f],0,_test_null=True,paused=True)
    try:
        token=s.editor('t','v')['editor_id'];time.sleep(.3)
        assert not s.status()['playing']
        assert s.editor_poll(token)['state']=='running'
        s.control('play')
        before=s.status()['position'];time.sleep(.1);assert s.status()['position']>before
        s.control('seek',500);s.control('pause')
        values=s.states()[0]['params'];key=next(k for k in values if k not in ('path','__mta_state_b64'))
        p.tracks[0].inserts[0].params[key]=.4;s.update(p)
        s.request('close_editor');deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            result=s.editor_poll(token)
            if result['state']=='completed':break
            time.sleep(.02)
        else:pytest.fail('Original live editor did not close')
        assert abs(result['params'][key]-.4)<1e-6 and not s.status()['failed']
    finally:s.close()


def test_linux_editor_guard_only_ignores_zero_window_probe_errors():
    from app.vst3_x11 import Error,transient
    assert transient(Error(resourceid=0,error_code=3,request_code=20))
    assert transient(Error(resourceid=0,error_code=3,request_code=2))
    assert not transient(Error(resourceid=123,error_code=3,request_code=20))
    assert not transient(Error(resourceid=0,error_code=10,request_code=20))


def test_ipc_atomic_publication_survives_temporary_windows_reader_lock(tmp_path,monkeypatch):
    from app import vst3_live as v
    replace=v.os.replace;calls=[]
    def locked(source,target):
        calls.append(target)
        if len(calls)<=2:raise PermissionError('Sharing violation')
        return replace(source,target)
    monkeypatch.setattr(v.os,'replace',locked)
    target=tmp_path/'status.json';target.write_text('{"old":true}')
    v.atomic(target,{'complete':True})
    assert __import__('json').loads(target.read_text())=={'complete':True}
    assert not list(tmp_path.glob('*.tmp'))
