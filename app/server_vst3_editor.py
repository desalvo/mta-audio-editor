"""Owner-scoped original-editor routes and durable, conflict-checked plugin state."""
import json
import re
import time
from fastapi import HTTPException,Request,Response


def persist(entry):
    edit=getattr(entry,'editor',None)
    if not edit or not edit.get('result'):return None
    from .storage import load_project,save_project
    from .ai_project_lock import project_publication_lock
    with project_publication_lock(entry.project):
        project=load_project(entry.project)
        if project.owner_user_id!=entry.session.project.owner_user_id:raise RuntimeError('Project ownership changed while the editor was open')
        track=next((t for t in project.tracks if t.id==edit['route']),None)
        item=track.instrument if track and edit['insert']=='instrument' else next((i for i in (track.inserts if track else project.master_inserts if edit['route']=='master' else []) if i.id==edit['insert']),None)
        if item is None or item.params!=edit['original']:raise RuntimeError('Plugin changed elsewhere. Original editor state was not applied.')
        values=edit['result']
        if not isinstance(values,dict) or len(json.dumps(values,allow_nan=False))>13*1024**2:raise RuntimeError('Invalid original editor state')
        before=len(project.model_dump_json().encode())
        item.params={'path':edit['original']['path'],**{k:v for k,v in values.items() if k!='path'}}
        from .main import _ensure_workspace_capacity
        _ensure_workspace_capacity(project.owner_user_id,max(0,len(project.model_dump_json().encode())-before))
        save_project(project)
        snapshot=entry.session.project
        route=next((t for t in snapshot.tracks if t.id==edit['route']),None)
        saved=route.instrument if route and edit['insert']=='instrument' else next((i for i in (route.inserts if route else snapshot.master_inserts if edit['route']=='master' else []) if i.id==edit['insert']),None)
        if saved is not None:saved.params=dict(item.params)
        entry.editor=None
        return project


def finish(entry,*,wait=False):
    edit=getattr(entry,'editor',None)
    if not edit:return None
    if not edit.get('result'):
        if wait:entry.session.request('close_editor')
        until=time.monotonic()+(5 if wait else 0)
        while True:
            result=entry.session.editor_poll(edit['id'])
            if result['state']=='completed':edit['result']=result['params'];break
            if not wait or time.monotonic()>=until:return None
            time.sleep(.02)
    return persist(entry)


def register_routes(app,entry_for):
    def editor_entry(pid,token,eid,request):
        entry,project=entry_for(request,pid,token)
        if not re.fullmatch('[0-9a-f]{32}',eid) or not getattr(entry,'editor',None) or entry.editor['id']!=eid:raise HTTPException(404,'Original plugin editor not found')
        return entry,project

    @app.post('/api/projects/{pid}/vst3-live/{token}/editor')
    def open_editor(pid:str,token:str,body:dict,request:Request):
        entry,project=entry_for(request,pid,token)
        with entry.session.lock:
            if getattr(entry,'editor',None):raise HTTPException(409,'Close the current original plugin editor first')
            route=body.get('route');iid=body.get('insert')
            snapshot=entry.session.project
            track=next((t for t in snapshot.tracks if t.id==route),None)
            item=track.instrument if track and iid=='instrument' else next((i for i in (track.inserts if track else snapshot.master_inserts if route=='master' else []) if i.id==iid),None)
            if not item or not item.enabled or item.plugin!='vst3':raise HTTPException(404,'Live plugin insert not found')
            try:
                value=entry.session.editor(route,iid)
                entry.editor={'id':value['editor_id'],'route':route,'insert':iid,'original':dict(item.params)}
                return value
            except (ValueError,RuntimeError,OSError) as exc:raise HTTPException(409,str(exc)) from exc

    @app.get('/api/projects/{pid}/vst3-live/{token}/editor/{eid}/frame')
    def frame(pid:str,token:str,eid:str,request:Request):
        entry,_=editor_entry(pid,token,eid,request)
        try:
            with entry.session.lock:
                result=entry.session.request('editor-frame');name=result['frame']
                if not re.fullmatch(r'frame-[0-9a-f]{32}\.jpg',name):raise RuntimeError('Invalid editor frame')
                path=entry.session.path/name
                try:
                    if path.stat().st_size>4*1024**2:raise RuntimeError('Editor frame too large')
                    return Response(path.read_bytes(),media_type='image/jpeg',headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
                finally:path.unlink(missing_ok=True)
        except (RuntimeError,OSError,ValueError) as exc:raise HTTPException(409,str(exc)) from exc

    @app.post('/api/projects/{pid}/vst3-live/{token}/editor/{eid}/input')
    def input_events(pid:str,token:str,eid:str,body:dict,request:Request):
        entry,_=editor_entry(pid,token,eid,request)
        events=body.get('events')
        if not isinstance(events,list) or len(events)>64 or len(json.dumps(events))>16384:raise HTTPException(422,'Invalid editor input batch')
        try:entry.session.request('editor-input',events);return {'ok':True}
        except (ValueError,RuntimeError,OSError) as exc:raise HTTPException(422,str(exc)) from exc

    @app.post('/api/projects/{pid}/vst3-live/{token}/editor/{eid}/state')
    def state(pid:str,token:str,eid:str,body:dict,request:Request):
        entry,_=editor_entry(pid,token,eid,request)
        try:
            with entry.session.lock:
                project=finish(entry,wait=body.get('close') is True)
                if project:return {'state':'completed','project':project.model_dump(mode='json')}
                return {'state':'running'}
        except (ValueError,RuntimeError,OSError) as exc:raise HTTPException(409,str(exc)) from exc
