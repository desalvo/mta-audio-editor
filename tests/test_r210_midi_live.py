"""Interactive monitoring, hardware scheduling and compiled host-clock regressions."""
# ruff: noqa: F811 -- pytest fixtures
import json
import os
from pathlib import Path
import struct
import subprocess
import time

import numpy as np
import pytest
from starlette.websockets import WebSocketDisconnect

from app import storage
from app.models import Project,Track,InsertPlugin,MidiNote,Clip
from app.midi_devices import validate_messages
from app.vst3_transport import HostClock,runtime_available
from test_r210_server_vst3 import server  # noqa: F401
from test_r210_live_vst3 import real_plugin  # noqa: F401
from test_r210_cpp_audio_engine import compiled_core  # noqa: F401
from test_r210_midi import instrument_path  # noqa: F401


@pytest.mark.parametrize('messages',[[[0xF0,1,2]],[[0x90,128,1]],[[0xC0,2,3]],[[True,1]],[[0x90,60,1]]*513])
def test_monitor_rejects_invalid_or_unbounded_midi(messages):
    with pytest.raises(ValueError):validate_messages(messages)


def test_compiled_host_clock_decimal_meter_seek_pause_and_loop(real_plugin):
    from pedalboard import load_plugin
    assert runtime_available(),'Build scripts/build_vst3_runtime.py --install before this release check'
    plugin=load_plugin(str(real_plugin))
    p=Project(id='clock',title='clock',bpm=123.45,base_bpm=123.45,time_signature='7/8')
    host=HostClock(p,48000);host.apply(plugin,48000)
    before=plugin._mta_transport
    # The project BPM counts eighth-note pulses in 7/8; VST host tempo is quarter-note BPM.
    assert before['bpm']==pytest.approx(123.45*4/8) and (before['numerator'],before['denominator'])==(7,8)
    assert before['ppq']==pytest.approx((123.45*4/8)/60)
    plugin.process(np.zeros((2,512),np.float32),48000,buffer_size=512,reset=False)
    assert plugin._mta_transport['sample']==48512
    host.playing=False;host.apply(plugin,12000)
    plugin.process(np.zeros((2,512),np.float32),48000,buffer_size=512,reset=False)
    assert plugin._mta_transport['sample']==12000 and not plugin._mta_transport['playing']
    host.data.update(vst_loop_enabled=True,vst_loop_start_ms=0,vst_loop_end_ms=4000)
    host.apply(plugin,96000);assert plugin._mta_transport['looping']
    host.override(72000,False,3000);assert host.context(9000)[3]==72000
    with pytest.raises(ValueError):host.override(float('nan'),True,0)


def instrument_project(server,monkeypatch):
    path=os.getenv('MTA_TEST_VSTI')
    if not path:pytest.skip('Set MTA_TEST_VSTI for real instrument monitoring')
    client,p,source,manager,login,user,other=server
    monkeypatch.setenv('MTA_VST3_PATHS',os.pathsep.join([str(source.parent),str(Path(path).parent)]))
    p.master_inserts=[]
    p.tracks=[Track(id='keys',name='Keys',filename=source.name,kind='midi',duration_ms=1000,channels=2,
                    instrument=InsertPlugin(id='instrument',plugin='vst3',params={'path':path}),
                    midi_notes=[MidiNote(pitch=40,duration_ms=1000)])]
    storage.save_project(p,_skip_flac_conversion=True)
    return client,p,manager,login,user,other


def test_real_websocket_monitor_notes_panic_transport_and_cleanup(server,monkeypatch):
    client,p,manager,*_=instrument_project(server,monkeypatch)
    with client.websocket_connect(f'/api/projects/{p.id}/midi-monitor/keys',headers={'origin':'http://testserver'}) as ws:
        assert ws.receive_json()['state']=='preparing'
        ready=ws.receive_json();assert ready['state']=='ready',ready
        def pull(sequence):
            ws.send_json({'op':'pull','sequence':sequence})
            payload=ws.receive_bytes();frames,rate=struct.unpack('<II',payload[:8])
            assert frames==1024 and rate==p.sample_rate
            return np.frombuffer(payload[8:],'<f4')
        # Stored notes must never leak into the audition bus.
        assert np.max(np.abs(pull(0)))<1e-7
        ws.send_json({'op':'transport','sample':48000,'playing':False})
        ws.send_json({'op':'midi','messages':[[144,64,110]]})
        samples=np.concatenate([pull(n) for n in range(1,7)])
        assert np.isfinite(samples).all() and np.max(np.abs(samples))>1e-5
        ws.send_json({'op':'panic'})
        ws.send_json({'op':'midi','messages':[[0xF0,1,2]]})
        assert ws.receive_json()['state']=='failed'
    assert not manager.entries
    assert len(storage.load_project(p.id).tracks[0].midi_notes)==1


def test_websocket_monitor_origin_and_project_ownership(server,monkeypatch):
    client,p,manager,login,_,other=instrument_project(server,monkeypatch)
    for origin in ('https://evil.example','null',''):
        with pytest.raises(WebSocketDisconnect),client.websocket_connect(f'/api/projects/{p.id}/midi-monitor/keys',headers={'origin':origin}):pass
    login(other)
    with pytest.raises(WebSocketDisconnect),client.websocket_connect(f'/api/projects/{p.id}/midi-monitor/keys',headers={'origin':'http://testserver'}):pass
    assert not manager.entries


def test_native_hardware_transport_chase_pause_seek_clock_and_cleanup(monkeypatch):
    from app import midi_devices
    sent=[];opened=[];closed=[]
    class Port:
        def __init__(self,name):opened.append(name)
        def send(self,msg):sent.append(list(msg))
        def panic(self):sent.append(['panic'])
        def close(self):closed.append(True)
    monkeypatch.setattr(midi_devices,'SharedOutput',Port)
    t=Track(id='keys',name='keys',filename='x.wav',kind='midi',midi_route='hardware',duration_ms=1000,
            midi_notes=[MidiNote(pitch=62,start_ms=0,duration_ms=900)],clips=[Clip(id="c",source_end_ms=1000)])
    p=Project(id='hw',title='hw',sample_rate=48000,tracks=[t]);state={'playing':False,'position':0}
    seq=midi_devices.Sequencer(p,{'outputs':{'keys':'Test output'},'clock':True},lambda:dict(state))
    def wait(predicate):
        deadline=time.monotonic()+2
        while not predicate():
            assert time.monotonic()<deadline
            time.sleep(.005)
    try:
        state.update(playing=True);wait(lambda:[144,62,100] in sent)
        assert [250] in sent and [248] in sent
        state.update(playing=False);wait(lambda:[252] in sent)
        sent.clear();state.update(position=24000);time.sleep(.03)
        assert [144,62,100] not in sent,'A paused seek must not sound held notes'
        state.update(playing=True);wait(lambda:[251] in sent)
        assert [144,62,100] in sent and any(m[0]==242 for m in sent)
    finally:seq.close()
    assert opened==['Test output'] and closed and not seq.thread.is_alive()


def test_browser_clip_mapping_matches_sample_scheduler():
    from app.midi import events
    t=Track(id='m',name='m',filename='x.wav',kind='midi',duration_ms=1000,delay_ms=-50,
            midi_notes=[MidiNote(start_ms=0,duration_ms=500,pitch=62)],
            clips=[Clip(id="c",source_start_ms=200,source_end_ms=800,timeline_start_ms=100)])
    root=Path(__file__).resolve().parents[1]
    result=subprocess.run(['node','-e','const m=require("./app/static/midi_rules.js");console.log(JSON.stringify(m.events(JSON.parse(process.argv[1]))))',t.model_dump_json()],cwd=root,capture_output=True,text=True,check=True)
    actual=[(x['at'],x['data']) for x in json.loads(result.stdout)]
    assert actual==events(t)


def test_server_transport_host_pause_resume_and_seek(server):
    from test_r210_server_vst3 import start
    client,p,*_=server
    route,_=start(client,p)
    pause=client.post(route+'/control',json={'action':'seek','cursor_ms':350,'playing':False})
    assert pause.status_code==200 and pause.json()['status']['host_playing'] is False
    assert pause.json()['status']['position_ms']==pytest.approx(350)
    resume=client.post(route+'/control',json={'action':'play'})
    assert resume.status_code==200 and resume.json()['status']['host_playing'] is True
    assert client.delete(route).status_code==200


def test_native_monitor_null_device_live_input_and_shutdown(compiled_core,instrument_path,monkeypatch,tmp_path):
    from app import cpp_audio
    from app.midi_monitor import monitor_project
    from app.vst3_live import Session
    monkeypatch.setenv('MTA_AUDIO_CORE_PATH',str(compiled_core));cpp_audio._load.cache_clear()
    track=Track(id='keys',name='keys',filename='anchor.wav',kind='midi',duration_ms=1000,
                instrument=InsertPlugin(id='instrument',plugin='vst3',params={'path':str(instrument_path)}))
    p=monitor_project(Project(id='native-monitor',title='monitor',sample_rate=48000,tracks=[track]),'keys')
    session=Session(p,[tmp_path/'unused.wav'],0,monitor=True,_test_null=True)
    process=session.proc;directory=session.path
    try:
        assert session.status()['host_sync']
        session.request('midi',[[144,67,110]])
        deadline=time.monotonic()+3
        while session.status().get('peak_left',0)<1e-5:
            assert time.monotonic()<deadline,session.status()
            time.sleep(.01)
        session.request('transport',{'sample':48000,'playing':False})
        session.request('panic')
    finally:session.close()
    assert process.poll() is not None and not directory.exists()


def test_native_input_bounded_callback_and_exclusive_shared_output(monkeypatch):
    import sys
    from types import SimpleNamespace
    from app import midi_devices
    devices=[]
    class Device:
        def __init__(self):self.closed=False;self.messages=[];devices.append(self)
        def get_ports(self):return ['Keys']
        def open_port(self,*_):pass
        def ignore_types(self,**_):pass
        def set_callback(self,fn):self.callback=fn
        def cancel_callback(self):pass
        def close_port(self):self.closed=True
        def delete(self):pass
        def send_message(self,data):self.messages.append(data)
    monkeypatch.setitem(sys.modules,'rtmidi',SimpleNamespace(MidiIn=Device,MidiOut=Device))
    incoming=midi_devices.Input('Keys')
    try:
        for _ in range(2050):incoming._receive(([144,60,100],0),None)
        assert incoming.dropped==1 and len(incoming.pending)<=2048
        assert [176,120,0] in incoming.drain()
        capture=incoming.capture();assert capture['connected'] and capture['dropped']==1
    finally:incoming.close()
    assert devices[0].closed
    a=midi_devices.SharedOutput('Keys');b=midi_devices.SharedOutput('Keys')
    assert len(devices)==2,'Exclusive drivers must see only one output open'
    a.close();assert not devices[-1].closed
    b.send([144,60,100]);b.close()
    assert devices[-1].closed and 'Keys' not in midi_devices.SharedOutput.pool


def test_native_bridge_note_order_and_panic_queue_bounds():
    root=Path(__file__).resolve().parents[1]
    subprocess.run(['node',str(root/'tests/midi_native_output.cjs')],cwd=root,check=True,timeout=10)
