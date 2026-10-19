"""Headless, persistent VST3 graph. Only runs in the isolated server worker.

Pull-driven PCM is bounded by the browser queue. No sound device is opened.
"""
import json
import math
import os
from pathlib import Path
import time
import threading
from queue import Queue,Empty

from .vst3_live import atomic


def run(config, root):
    import numpy as np
    from .models import Project
    from .vst3_live_graph import Graph
    from .audio_backend import _SCOPE
    _SCOPE.set('cpp')  # Immutable worker choice; never read server settings after confinement.
    project=Project.model_validate(config['project']);graph=None;paths=[];sequence=0
    desktop=None;display_error='';quit=threading.Event();editor_close=threading.Event();editor_active=threading.Event();editors=Queue()
    try:
        from .server_vst3_display import Desktop,available,unavailable_reason
        from .vst3_sandbox import private_environment,confine
        if config.get('original_editor',True):private_environment(root)
        if config.get('original_editor',True) and available():
            try:desktop=Desktop(root)
            except (RuntimeError,OSError) as exc:display_error=str(exc)
        else:display_error=unavailable_reason()
        # Preparation remains inside this killable process group, including FFmpeg.
        limit=max(16*1024**2,min(64*1024**3,int(os.getenv('MTA_SERVER_VST3_DRY_LIMIT_BYTES',str(4*1024**3)))))
        if os.name=='posix':
            import resource
            resource.setrlimit(resource.RLIMIT_FSIZE,(limit,limit))
        if desktop and os.getenv('MTA_VST3_DISPLAY_TEST_TCP')!='1':
            from .vst3_host import vst3_roots
            try:confine(root,config['paths'],vst3_roots()+[Path(os.getenv('MTA_AUDIO_CORE_PATH','/nonexistent'))])
            except (OSError,RuntimeError) as exc:
                desktop.close();desktop=None;display_error=str(exc)
        from .live_sources import prepare
        def progress(done,total,track):atomic(root/'preparation.json',{'stage':'sources','done':done,'total':total,'track':track})
        paths,raw_sources=prepare(project,config['paths'],root,progress)
        atomic(root/'preparation.json',{'stage':'graph','done':len(paths),'total':len(paths),'track':''})
        used=sum(path.stat().st_size for path in paths if path.parent==root)
        if used>limit:raise RuntimeError('VST3 prepared audio exceeds the server session disk limit')
        graph=Graph(project,paths,round(config['cursor_ms']*project.sample_rate/1000),raw_sources=raw_sources)
        if config.get('host_transport') is not None:graph.host.data=config['host_transport']
        if config.get('monitor'):graph.host.override(0,False,0)
        def snapshot():
            return {'active':True,'position_ms':graph.position*1000/graph.rate,'position':graph.position,
                    'rate':graph.rate,'total':graph.total,'physical':False,'playing':False,
                    'ended':graph.position>=graph.total,'failed':False,'meters':graph.meters,'plugin_count':len(graph.plugins),
                    'server_live_vst3':True,'host_bpm':graph.host.context(round(graph.position*graph.ratio))[0],'original_editor_available':desktop is not None,'sequence':sequence,'host_playing':graph.host.context(round(graph.position*graph.ratio))[5]}
        atomic(root/'status.json',snapshot());atomic(root/'ready.json',{'ok':True})
        def work():
            nonlocal graph,sequence,project
            try:
                last=0
                while not quit.is_set():
                    for path in sorted(root.glob('cmd-*.json'))[:32]:
                        data=json.loads(path.read_text());path.unlink();token=data['id'];action=data['action'];value=data.get('value')
                        try:
                            if action=='stop':quit.set();editor_close.set();return
                            if action=='read':
                                if not isinstance(value,dict) or value.get('sequence')!=sequence:raise ValueError('PCM sequence mismatch')
                                count=value.get('frames',32768)
                                if type(count) is not int or not 1024<=count<=32768:raise ValueError('PCM block size must be 1024–32768')
                                start=graph.position;pcm=graph.read(count)
                                if not np.isfinite(pcm).all():raise RuntimeError('VST3 produced non-finite samples')
                                target=root/('pcm-'+token+'.bin');target.write_bytes(pcm.astype('<f4',copy=False).tobytes())
                                sequence+=1
                                result={'chunk':target.name,'frames':len(pcm),'rate':graph.rate,'channels':2,'start_frame':start,'sequence':sequence,'ended':graph.position>=graph.total,'meters':graph.meters}
                            elif action=='editor':
                                if desktop is None:raise ValueError(display_error)
                                if editor_active.is_set():raise ValueError('Close the current original plugin editor first')
                                node=graph.plugins.get((value.get('route'),value.get('insert'))) if isinstance(value,dict) else None
                                if node is None:raise ValueError('Live plugin insert not found')
                                editor_close.clear();editor_active.set();editors.put((token,node))
                                result={'editor_id':token,'width':desktop.width,'height':desktop.height}
                            elif action=='close_editor':editor_close.set();result={}
                            elif action=='editor-frame':
                                if desktop is None or not editor_active.is_set():raise ValueError('Plugin editor is not open')
                                (root/('frame-'+token+'.jpg')).write_bytes(desktop.frame());result={'frame':'frame-'+token+'.jpg'}
                            elif action=='editor-input':
                                if desktop is None or not editor_active.is_set():raise ValueError('Plugin editor is not open')
                                desktop.input(value);result={}
                            elif action=='seek':
                                if type(value) not in (float,int) or not math.isfinite(value) or value<0:raise ValueError('Invalid seek')
                                position=min(graph.total,round(value*graph.rate/1000));reuse=graph.plugins
                                was=graph.host.playing;graph.close();graph=Graph(project,paths,position,reuse=reuse,raw_sources=raw_sources);graph.set_playing(was);sequence=0
                                result={'status':snapshot()}
                            elif action=='update':
                                new=Project.model_validate(value)
                                if editor_active.is_set():
                                    wanted=[(t.id,t.instrument,t.inserts) for t in new.tracks]+[('master',None,new.master_inserts)]
                                    previous=[(t.id,t.instrument,t.inserts) for t in project.tracks]+[('master',None,project.master_inserts)]
                                    if wanted!=previous:raise ValueError('Close the original plugin editor before changing the effect chain')
                                if not graph.update(new):
                                    position=graph.position;reuse=graph.plugins;was=graph.host.playing;graph.close();graph=Graph(new,paths,position,reuse=reuse,raw_sources=raw_sources);graph.set_playing(was)
                                project=new;result={'status':snapshot()}
                            elif action in ('play','pause'):
                                graph.set_playing(action=='play');result={'status':snapshot()}
                            elif action=='states':
                                result={'states':[{'route':route,'insert':insert,'params':node.values()} for (route,insert),node in graph.plugins.items()]}
                            elif action=='ump':
                                if not config.get('monitor'):raise ValueError('Not a monitoring session')
                                graph.live_ump(project.tracks[0].id,value);result={}
                            elif action=='midi':
                                if not config.get('monitor'):raise ValueError('Not a monitoring session')
                                graph.live_midi(project.tracks[0].id,value);result={}
                            elif action=='panic':graph.panic();result={}
                            elif action=='midi-parameters':
                                if not config.get('monitor'):raise ValueError('Not a monitoring session')
                                graph.live_parameters(value);result={}
                            elif action=='transport':
                                if not config.get('monitor') or not isinstance(value,dict):raise ValueError('Invalid monitor transport')
                                graph.host.override(value.get('sample'),value.get('playing'),graph.position);result={}
                            else:raise ValueError('Unknown server VST3 command')
                            atomic(root/('reply-'+token+'.json'),{'ok':True,**result})
                        except (ValueError,TypeError) as exc:
                            atomic(root/('reply-'+token+'.json'),{'ok':False,'error':str(exc)})
                        # DSP/runtime errors are fatal: the parent closes the session. No dry fallback.
                    if time.monotonic()-last>.1:
                        atomic(root/'status.json',snapshot());last=time.monotonic()
                    time.sleep(.005)
            except BaseException as exc:
                atomic(root/'status.json',{'active':False,'failed':True,'error':str(exc)})
                quit.set();editor_close.set()
        thread=threading.Thread(target=work,name='mta-server-vst3-dsp',daemon=True);thread.start()
        while not quit.is_set():
            try:token,node=editors.get(timeout=.02)
            except Empty:continue
            try:
                from .vst3_x11 import editor_errors
                with editor_errors():node.plugin.show_editor(editor_close)
                result={'params':node.values()};node.item.params=dict(result['params'])
            except Exception as exc:result={'error':str(exc)}
            if desktop:desktop.release()
            atomic(root/('editor-'+token+'.json'),result);editor_active.clear()
        thread.join(timeout=2)
        if thread.is_alive():os._exit(1)
        return 0
    except BaseException as exc:
        atomic(root/'status.json',{'active':False,'failed':True,'error':str(exc)})
        if not (root/'ready.json').exists():atomic(root/'ready.json',{'ok':False,'error':str(exc)})
        return 1
    finally:
        if graph is not None:graph.close()
        if desktop:desktop.close()
