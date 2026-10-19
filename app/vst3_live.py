"""Native live VST3 process supervisor and bounded file IPC (also frozen GUI builds).

No plugin code is loaded in the application or device callback. A hung/crashed
worker can be terminated without joining its DSP thread in the application.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import uuid


def available():
    try:return all(importlib.util.find_spec(x) is not None for x in ('pedalboard','av'))
    except (ImportError,ValueError):return False


def atomic(path,data):
    tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        tmp.write_text(json.dumps(data,allow_nan=False),encoding='utf-8')
        # Windows readers may briefly deny replacement of an open status file.
        # Retry on this non-audio thread; never publish a partially written file.
        for attempt in range(25):
            try:os.replace(tmp,path);break
            except PermissionError:
                if attempt==24:raise
                time.sleep(.002)
    finally:tmp.unlink(missing_ok=True)


def command(config):
    if getattr(sys,'frozen',False):return [sys.executable,'--vst3-worker','--live-config',str(config)]
    return [sys.executable,'-m','app.vst3_host','--live-config',str(config)]


class Session:
    def __init__(self,project,paths,cursor_ms,cancelled=lambda:False,*,_test_null=False,paused=False,output='device',startup_timeout=60,monitor=False,midi_options=None,original_editor=True,host_transport=None,raw_sources=(),on_progress=None):
        if not available():raise RuntimeError('Live VST3 requires the native Pedalboard/PyAV runtime. Update this application.')
        self.project=project.model_copy(deep=True);self.lock=threading.RLock();self.root=tempfile.TemporaryDirectory(prefix='mta-vst3-live-');self.path=Path(self.root.name);self.proc=None;self.midi_output=None;self.midi_options=midi_options or {}
        if output not in ('device','browser'):raise ValueError('Invalid live output')
        self.process_group=output=='browser' and os.name=='posix'
        self.log=(self.path/'worker.log').open('wb');self.closed=False;self.last={};self.edited=False
        config=self.path/'config.json'
        atomic(config,{'project':project.model_dump(mode='json'),'paths':[str(p) for p in paths],'cursor_ms':cursor_ms,'test_null':_test_null,'paused':paused,'output':output,'monitor':monitor,'midi_options':midi_options or {},'original_editor':original_editor,'host_transport':host_transport,'raw_sources':list(raw_sources)})
        try:
            worker_env=None
            if output=='browser':
                from .vst3_sandbox import worker_environment
                from .vst3_host import vst3_roots
                worker_env=worker_environment();worker_env['MTA_VST3_PATHS']=os.pathsep.join(map(str,vst3_roots()))
            self.proc=subprocess.Popen(command(config),env=worker_env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=self.log,start_new_session=self.process_group)
            deadline=time.monotonic()+startup_timeout
            while not (self.path/'ready.json').exists():
                progress=self.path/'preparation.json'
                if on_progress and progress.is_file() and progress.stat().st_size<16384:
                    try:on_progress(json.loads(progress.read_text()))
                    except (OSError,ValueError):pass
                if cancelled():raise RuntimeError('Native playback preparation cancelled')
                if self.proc.poll() is not None:raise RuntimeError('Live VST3 worker failed to start: '+self.error())
                if time.monotonic()>deadline:raise RuntimeError('Live VST3 initialization timed out')
                time.sleep(.02)
            result=json.loads((self.path/'ready.json').read_text())
            if not result['ok']:raise RuntimeError(result.get('error','Live VST3 initialization failed'))
            self.last=self.status()
            if output=='device' and not monitor and midi_options and (midi_options.get('outputs') or midi_options.get('ump_outputs')):
                from .midi_devices import Sequencer
                self.midi_output=Sequencer(project,midi_options,self.status)
        except BaseException:self.close();raise

    def error(self):
        try:return (self.path/'worker.log').read_text(errors='replace')[-1600:]
        except OSError:return ''

    def status(self):
        if self.closed:raise RuntimeError('Live VST3 session is closed')
        path=self.path/'status.json'
        try:self.last=json.loads(path.read_text())
        except (FileNotFoundError,json.JSONDecodeError):pass
        if self.proc.poll() is not None:return {**self.last,'failed':True,'error':self.last.get('error') or 'VST3 worker exited: '+self.error()}
        if path.exists() and time.time()-path.stat().st_mtime>5:
            self.proc.terminate();return {**self.last,'failed':True,'error':'VST3 worker stopped responding'}
        if self.midi_output and self.midi_output.error:return {**self.last,'failed':True,'midi_error':self.midi_output.error,'error':self.midi_output.error}
        return {**self.last,'live_vst3':True}

    def request(self,action,value=None,timeout=10):
        with self.lock:
            if self.closed:raise RuntimeError('Live VST3 session is closed')
            token=uuid.uuid4().hex;reply=self.path/('reply-'+token+'.json')
            atomic(self.path/('cmd-'+token+'.json'),{'id':token,'action':action,'value':value})
            deadline=time.monotonic()+timeout
            while not reply.exists():
                if self.proc.poll() is not None:raise RuntimeError('VST3 worker exited: '+self.error())
                if time.monotonic()>deadline:
                    self.proc.terminate();raise RuntimeError('VST3 worker control timed out')
                time.sleep(.005)
            result=json.loads(reply.read_text());reply.unlink()
            if not result.get('ok'):raise RuntimeError(result.get('error','VST3 command failed'))
            return result

    def control(self,action,value=0):
        if action=='status':return self.status()
        return self.request(action,value)['status']

    def update(self,project):
        def sources(p):
            return [(t.id,t.filename,t.delay_ms,t.channels,[c.model_dump() for c in t.clips],t.master_bypass,t.kind,t.midi_route,[n.model_dump() for n in t.midi_notes],[c.model_dump() for c in t.midi_controls],[s.model_dump() for s in t.midi_sysex],[u.model_dump() for u in t.midi_ump],t.mpe_zone,t.mpe_members,t.mpe_pitch_bend) for t in p.tracks],p.sample_rate,p.bpm,p.base_bpm,p.pitch_semitones,p.timeline_end_ms
        if sources(project)!=sources(self.project):return {'requires_prepare':True}
        refresh_midi=self.midi_output and [(t.mute,t.solo) for t in project.tracks]!=[(t.mute,t.solo) for t in self.project.tracks]
        result=self.request('update',project.model_dump(mode='json'),timeout=30);self.project=project.model_copy(deep=True)
        if refresh_midi:
            from .midi_devices import Sequencer
            self.midi_output.close();self.midi_output=None
            self.midi_output=Sequencer(project,self.midi_options,self.status)
        return result

    def editor(self,route,insert):
        result=self.request('editor',{'route':route,'insert':insert});self.edited=True;return result

    def states(self):return self.request('states',timeout=2)['states'] if self.edited else []

    def editor_poll(self,token):
        path=self.path/('editor-'+token+'.json')
        if not path.exists():
            if self.status().get('failed'):raise RuntimeError('Live plugin editor stopped with the audio worker')
            return {'state':'running'}
        result=json.loads(path.read_text());path.unlink()
        if result.get('error'):raise RuntimeError(result['error'])
        return {'state':'completed','params':result['params']}

    def close(self):
        if self.closed:return
        if self.midi_output:self.midi_output.close();self.midi_output=None
        if self.proc and self.proc.poll() is None:
            try:self.request('stop',timeout=.5)
            except (RuntimeError,OSError):pass
        self.closed=True
        if self.proc and self.process_group:
            import signal
            try:os.killpg(self.proc.pid,signal.SIGTERM)
            except ProcessLookupError:pass
        if self.proc and self.proc.poll() is None:
            try:self.proc.terminate();self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:self.proc.kill();self.proc.wait(timeout=2)
        if self.proc and self.process_group:
            import signal
            try:os.killpg(self.proc.pid,signal.SIGKILL)
            except ProcessLookupError:pass
        self.log.close();self.root.cleanup()


def run(config):
    """Entry point on process main thread, which also owns plugin editor windows."""
    cfg=json.loads(Path(config).read_text());root=Path(config).parent
    if cfg.get('output')=='browser':
        from .server_vst3_worker import run as browser_run
        return browser_run(cfg,root)
    from queue import Queue,Empty
    from .models import Project
    from .native_transport import StreamDevice
    from .vst3_live_graph import Graph,BLOCK
    project=Project.model_validate(cfg['project']);paths=cfg['paths'];lock=threading.RLock();quit=threading.Event();editor_close=threading.Event();editors=Queue();builds=Queue();editor_active=threading.Event();graph=None;device=None;midi_input=None;midi_output=None
    try:
        graph=Graph(project,paths,round(cfg['cursor_ms']*project.sample_rate/1000),raw_sources=cfg.get('raw_sources',()))
        device=StreamDevice(graph.rate,graph.total,_test_null=cfg.get('test_null') is True)
        from .midi_devices import Input
        options=cfg.get('midi_options',{})
        if cfg.get('monitor') and options.get('input'):midi_input=Input(options['input'],sysex=bool(options.get('sysex',False)))
        graph.set_playing(not cfg.get('paused') and not cfg.get('monitor'))
        if graph.position:device.control('seek',graph.position*1000/graph.rate)
        if not cfg.get('paused'):
            for _ in range(3):
                pcm=graph.read()
                if len(pcm):device.push(pcm)
        if not cfg.get('paused'):device.control('play')
        def snapshot():return {**device.status(),'active':True,'live_vst3':True,'buffered_frames':device.buffered(),'meters':graph.meters,'plugin_count':len(graph.plugins),'midi_error':midi_output.error if midi_output else '','host_sync':all(hasattr(n.plugin,'_mta_set_transport') for n in graph.plugins.values())}
        atomic(root/'status.json',snapshot());atomic(root/'ready.json',{'ok':True})
        def rebuild(new,position):
            wanted={(route,i.id):i.params.get('path') for route,items in [(t.id,t.inserts) for t in new.tracks]+[('master',new.master_inserts)] for i in items if i.enabled and i.plugin=='vst3'}
            wanted.update({(t.id,'instrument'):t.instrument.params.get('path') for t in new.tracks if t.kind=='midi' and t.instrument and t.instrument.enabled})
            existing={key:node.item.params.get('path') for key,node in graph.plugins.items()}
            if wanted==existing:return Graph(new,paths,position,reuse=graph.plugins,raw_sources=cfg.get('raw_sources',()))
            if editor_active.is_set():raise RuntimeError('Close the live plugin editor before changing the effect chain')
            task={'project':new,'position':position,'done':threading.Event()};builds.put(task)
            if not task['done'].wait(30):raise RuntimeError('Live graph initialization timed out')
            if 'error' in task:raise RuntimeError(task['error'])
            return task['graph']
        def loop():
            nonlocal graph,project
            last=0;last_commands=0;finished=False
            try:
                while not quit.is_set():
                    with lock:
                        commands=sorted(root.glob('cmd-*.json'))[:64] if time.monotonic()-last_commands>.008 else []
                        if time.monotonic()-last_commands>.008:last_commands=time.monotonic()
                        for path in commands:
                            data=json.loads(path.read_text());path.unlink();action=data['action'];value=data.get('value');token=data['id']
                            try:
                                if action=='stop':quit.set();editor_close.set()
                                elif action=='update':
                                    new=Project.model_validate(value)
                                    if not graph.update(new):
                                        was=device.status()['playing'];position=device.status()['position'];device.control('pause');graph.close()
                                        graph=rebuild(new,position);device.control('seek',position*1000/graph.rate);finished=False
                                        graph.set_playing(was)
                                        if was:device.control('play')
                                    project=new
                                elif action=='seek':
                                    if type(value) not in (float,int) or not math.isfinite(value) or value<0:raise ValueError('Invalid seek')
                                    was=device.status()['playing'];position=min(graph.total,round(value*graph.rate/1000));device.control('pause');graph.close()
                                    graph=rebuild(project,position);device.control('seek',position*1000/graph.rate);finished=False
                                    graph.set_playing(was)
                                    if was:device.control('play')
                                elif action=='ump':graph.live_ump(project.tracks[0].id,value)
                                elif action=='midi':graph.live_midi(project.tracks[0].id,value)
                                elif action=='panic':graph.panic()
                                elif action=='midi-parameters':graph.live_parameters(value)
                                elif action=='midi-input':
                                    capture=midi_input.capture() if midi_input else {'events':[],'connected':False}
                                    atomic(root/('reply-'+token+'.json'),{'ok':True,**capture});continue
                                elif action=='transport':graph.host.override(value['sample'],value['playing'],graph.position)
                                elif action=='close_editor':editor_close.set()
                                elif action=='states':
                                    states=[{'route':route,'insert':insert,'params':node.values()} for (route,insert),node in graph.plugins.items()]
                                    if len(json.dumps(states))>32*1024*1024:raise RuntimeError('Live plugin states exceed the storage limit')
                                    atomic(root/('reply-'+token+'.json'),{'ok':True,'states':states});continue
                                elif action=='editor':
                                    node=graph.plugins.get((value['route'],value['insert']))
                                    if node is None:raise ValueError('Live plugin insert not found')
                                    if editor_active.is_set():raise RuntimeError('A live plugin editor is already open')
                                    editor_active.set();editors.put((token,node));atomic(root/('reply-'+token+'.json'),{'ok':True,'editor_id':token});continue
                                elif action in ('play','pause','gain'):
                                    if action in ('play','pause'):graph.set_playing(action=='play')
                                    device.control(action,value)
                                else:raise ValueError('Unknown live command')
                                current=snapshot();atomic(root/'status.json',current);atomic(root/('reply-'+token+'.json'),{'ok':True,'status':current})
                            except Exception as e:atomic(root/('reply-'+token+'.json'),{'ok':False,'error':str(e)})
                        if midi_input:
                            messages=midi_input.drain()
                            if messages:graph.live_midi(project.tracks[0].id,messages)
                        if not finished and device.buffered()<=BLOCK*2 and (device.status()['playing'] or cfg.get('monitor')):
                            pcm=graph.read()
                            if len(pcm):device.push(pcm)
                            else:device.finish();finished=True
                        if time.monotonic()-last>(.004 if options.get('outputs') else .04):atomic(root/'status.json',snapshot());last=time.monotonic()
                    time.sleep(.001)
            except BaseException as e:
                device.control('pause');atomic(root/'status.json',{**snapshot(),'failed':True,'error':str(e)});quit.set();editor_close.set()
        thread=threading.Thread(target=loop,name='mta-vst3-dsp',daemon=True);thread.start()
        while not quit.is_set():
            try:
                task=builds.get_nowait()
                try:task['graph']=Graph(task['project'],paths,task['position'],raw_sources=cfg.get('raw_sources',()))
                except Exception as e:task['error']=str(e)
                finally:task['done'].set()
            except Empty:pass
            try:token,node=editors.get(timeout=.01)
            except Empty:continue
            editor_close.clear()
            try:
                from .vst3_x11 import editor_errors
                with editor_errors():node.plugin.show_editor(editor_close)
                with lock:result={'params':node.values()}
            except Exception as e:result={'error':str(e)}
            editor_active.clear();atomic(root/('editor-'+token+'.json'),result)
        thread.join(timeout=2)
        if thread.is_alive():os._exit(1)  # bounded worker-only shutdown, never join a hung plugin in the app
    except BaseException as e:
        atomic(root/'ready.json',{'ok':False,'error':str(e)});raise
    finally:
        if midi_input:midi_input.close()
        if midi_output:midi_output.close()
        if device:device.close()
        if graph:graph.close()
    return 0


# Imports needed only inside the isolated run path, not readiness probes.
import math  # noqa: E402

