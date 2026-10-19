"""Frozen dispatch, restored opaque plugin state and original GUI worker output."""
import base64
import json
from pathlib import Path
import sys
import types
from app import vst3_host as host


def test_worker_commands_dispatch_frozen_executable_without_python_m(monkeypatch):
    monkeypatch.setattr(sys,'frozen',True,raising=False)
    cmd=host.worker_command('--inspect-plugin','some plugin.vst3')
    assert cmd==[sys.executable,'--vst3-worker','--inspect-plugin','some plugin.vst3']


def test_state_restore_precedes_explicit_parameter_override():
    class Param:
        raw_value=.2
    class Plugin:
        parameters={'gain':Param()}
        raw_state=b''
    plugin=Plugin();host.apply_parameters(plugin,{'__mta_state_b64':base64.b64encode(b'plugin data').decode(),'gain':.7})
    assert plugin.raw_state==b'plugin data' and plugin.parameters['gain'].raw_value==.7


def test_editor_runs_in_worker_and_persists_opaque_state(tmp_path,monkeypatch):
    class Param:
        raw_value=.5
    class Plugin:
        parameters={'gain':Param()}
        raw_state=b'initial'
        def show_editor(self):self.raw_state=b'edited';self.parameters['gain'].raw_value=.8
    monkeypatch.setitem(sys.modules,'pedalboard',types.SimpleNamespace(load_plugin=lambda p:Plugin()))
    monkeypatch.setattr(host,'validate_plugin_path',lambda p:Path(p))
    source=tmp_path/'parameters.json';source.write_text('{}');result=tmp_path/'state.json'
    monkeypatch.setattr(sys,'argv',['worker','--editor-plugin','Example.vst3','--editor-result',str(result),'--parameters-file',str(source)])
    assert host.main()==0
    values=json.loads(result.read_text());assert values['gain']==.8 and base64.b64decode(values['__mta_state_b64'])==b'edited'


def test_inspection_works_without_stdout_for_windowed_frozen_workers(tmp_path,monkeypatch):
    target=tmp_path/'inspection.json'
    monkeypatch.setattr(host,'validate_plugin_path',lambda p:Path(p));monkeypatch.setattr(host,'inspect_parameters',lambda p,**kw:{'parameters':[{'name':'gain','value':.5}],'is_instrument':False})
    monkeypatch.setattr(sys,'argv',['worker','--inspect-plugin','Example.vst3','--inspect-result',str(target)])
    assert host.main()==0 and json.loads(target.read_text())['parameters'][0]['name']=='gain'


def test_interleaved_native_and_vst_inserts_preserve_order_and_mono_upmix(tmp_path,monkeypatch):
    import subprocess
    import numpy as np
    import soundfile as sf
    from app import audio_engine as engine
    from app.models import Track,InsertPlugin
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER','false')
    source=tmp_path/'in.wav';sf.write(source,np.full(4800,.4),48000,subtype='FLOAT')
    first=tmp_path/'First.vst3';second=tmp_path/'Second.vst3';first.mkdir();second.mkdir()
    monkeypatch.setattr(host,'vst3_roots',lambda:[tmp_path.resolve()])
    monkeypatch.setattr(engine,'chain_filter',lambda items:'volume=0.5' if items else '')
    original=subprocess.run;calls=[]
    def worker(cmd,*args,**kwargs):
        if '--process' not in cmd:return original(cmd,*args,**kwargs)
        i=cmd.index('--process');a,b=Path(cmd[i+1]),Path(cmd[i+2]);data,rate=sf.read(a,always_2d=True)
        calls.append(data.copy());sf.write(b,data*data,rate,subtype='FLOAT')
        return subprocess.CompletedProcess(cmd,0,'','')
    monkeypatch.setattr(subprocess,'run',worker)
    inserts=[InsertPlugin(id='first',plugin='vst3',params={'path':str(first)}),InsertPlugin(id='middle',plugin='limiter'),InsertPlugin(id='second',plugin='vst3',params={'path':str(second)})]
    track=Track(id='a',name='A',filename='in.wav',channels=1,sample_rate=48000,duration_ms=100,inserts=inserts)
    target=tmp_path/'out.wav';engine.render_track(track,source,target,sample_rate=48000)
    data,rate=sf.read(target,always_2d=True)
    assert rate==48000 and data.shape==(4800,2) and len(calls)==2
    np.testing.assert_allclose(calls[1],.04,atol=1e-6);np.testing.assert_allclose(data,.0016,atol=1e-6)


def test_frozen_dispatch_never_starts_a_second_application(monkeypatch):
    from native import mta_audio_editor_native as launcher
    monkeypatch.setattr(sys,'argv',['MTA.exe','--vst3-worker','--inspect-plugin','Example.vst3'])
    monkeypatch.setattr(host,'main',lambda:0)
    monkeypatch.setattr(launcher,'_start_server',lambda *_:(_ for _ in ()).throw(AssertionError('A plugin worker must not start the app')))
    assert launcher.main()==0 and sys.argv[0]=='mta-vst3-worker'
