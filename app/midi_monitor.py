"""Dedicated interactive audition bus; never overwrites project notes or audio."""
import asyncio
import json
import struct
import time
from urllib.parse import urlsplit

from fastapi import HTTPException,Request,WebSocket,WebSocketDisconnect

from .models import Clip


def monitor_project(project,tid):
    track=next((t for t in project.tracks if t.id==tid and t.kind=='midi'),None)
    if not track or track.midi_route=='hardware' or not track.instrument or not track.instrument.enabled:raise ValueError('Select an enabled VST instrument for monitoring')
    result=project.model_copy(deep=True);track=track.model_copy(deep=True)
    track.midi_notes=[];track.midi_controls=[];track.midi_sysex=[];track.midi_ump=[];track.delay_ms=0;track.midi_route='instrument';track.master_bypass=False
    track.mute=False;track.solo=False;track.duration_ms=86400000;track.clips_initialized=True
    track.clips=[Clip(id='monitor',source_end_ms=86400000)]
    result.tracks=[track];result.timeline_end_ms=86400000;result.base_bpm=result.bpm
    result.master_fade_enabled=False;result.pitch_semitones=0
    return result


def register_routes(app,project_for_actor,actor):
    @app.websocket('/api/projects/{pid}/midi-monitor/{tid}')
    async def monitor(websocket:WebSocket,pid:str,tid:str):
        from . import server_vst3
        from .audio_backend import selected
        from .storage import audio_path,validate_project_files
        from .vst3_transport import runtime_available
        from .midi_devices import validate_messages
        token=None;accepted=False
        try:
            # Session cookies are accepted only from the same origin. No API
            # secrets enter URLs, and WebSocket writes cannot bypass CSRF.
            origin=websocket.headers.get('origin','');expected=websocket.headers.get('host','')
            parsed=urlsplit(origin)
            if parsed.netloc!=expected or parsed.scheme not in ('http','https'):
                await websocket.close(code=1008);return
            request=Request({**websocket.scope,'type':'http','method':'GET'})
            project=project_for_actor(request,pid);owner=actor(request)['id']
            if selected()!='cpp' or not runtime_available():raise ValueError('Monitoring requires the updated C++ VST transport runtime')
            validate_project_files(project);project=monitor_project(project,tid)
            await websocket.accept()
            accepted=True
            # Limits and expiry are shared with normal playback sessions.
            value=server_vst3.sessions.start(owner,project,[audio_path(pid,t.filename) for t in project.tracks],'monitor-'+str(id(websocket)),0,asynchronous=True,monitor=True)
            token=value['session_id'];await websocket.send_json({'state':'preparing'})
            while True:
                entry=server_vst3.sessions.get(token,owner,pid,allow_preparing=True)
                if entry.error:raise ValueError(entry.error)
                if entry.session:break
                # Detect a disconnect/cancel even while a plugin is loading.
                try:
                    message=await asyncio.wait_for(websocket.receive(),timeout=.1)
                    if message['type']=='websocket.disconnect':return
                    if len(message.get('text') or '')>16384:raise ValueError('MIDI message too large')
                    if message.get('text') and json.loads(message['text']).get('op')=='stop':return
                except asyncio.TimeoutError:pass
            await websocket.send_json({'state':'ready','session_id':token,'rate':project.sample_rate,'channels':2,'block':1024})
            sequence=0;window=time.monotonic();messages=0
            while True:
                raw=await asyncio.wait_for(websocket.receive_text(),timeout=15)
                if len(raw)>262144:raise ValueError('MIDI message too large')
                now=time.monotonic()
                if now-window>=1:window=now;messages=0
                messages+=1
                if messages>600:raise ValueError('MIDI monitor request rate exceeded')
                server_vst3.sessions.get(token,owner,pid)
                data=json.loads(raw);op=data.get('op')
                if op=='stop':return
                if op=='midi':await asyncio.to_thread(entry.session.request,'midi',validate_messages(data.get('messages'),sysex=websocket.query_params.get('sysex')=='1'))
                elif op=='ump':await asyncio.to_thread(entry.session.request,'ump',data.get('messages'))
                elif op=='panic':await asyncio.to_thread(entry.session.request,'panic')
                elif op=='parameters':await asyncio.to_thread(entry.session.request,'midi-parameters',data.get('params'))
                elif op=='transport':await asyncio.to_thread(entry.session.request,'transport',{'sample':data.get('sample'),'playing':data.get('playing')})
                elif op=='pull':
                    if data.get('sequence')!=sequence:raise ValueError('Monitoring sequence mismatch')
                    result,pcm=await asyncio.to_thread(server_vst3.read_pcm,entry.session,sequence,1024)
                    sequence=result['sequence']
                    await websocket.send_bytes(struct.pack('<II',result['frames'],result['rate'])+pcm)
                elif op=='heartbeat':await websocket.send_json({'state':'alive'})
                else:raise ValueError('Unsupported MIDI monitoring command')
        except (WebSocketDisconnect,asyncio.TimeoutError):pass
        except (HTTPException,ValueError,TypeError,KeyError,RuntimeError,OSError) as exc:
            try:
                if accepted:await websocket.send_json({'state':'failed','error':str(exc)})
                await websocket.close(code=1008)
            except (RuntimeError,WebSocketDisconnect):pass
        finally:
            if token:await asyncio.to_thread(server_vst3.sessions.close,token)
