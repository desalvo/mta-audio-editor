"""Server administrator model-file maintenance; no inference or rights grants."""
import os
from pathlib import Path
import tempfile
import uuid
from fastapi import HTTPException,Request,Query
from fastapi.responses import StreamingResponse
from . import model_asset_admin as models
from . import ai_arranger_runtime as queue


def register_routes(app,actor):
    def admin(request):
        user=actor(request)
        if user.get('role')!='admin':raise HTTPException(403,'Administrator required')
        return user

    @app.get('/api/admin/ai/model-assets')
    def inventory(request:Request,engine:str='',search:str=Query('',max_length=200),offset:int=Query(0,ge=0),limit:int=Query(100,ge=1,le=250)):
        admin(request)
        try:return {**models.inventory(engine,search,offset,limit),'recipes':models.recipes()}
        except (ValueError,OSError) as exc:raise HTTPException(409,str(exc)) from exc

    @app.delete('/api/admin/ai/model-assets/bundles/{asset_id}')
    def remove_bundle(asset_id:str,request:Request):
        admin(request)
        try:return models.remove_bundle(asset_id)
        except (ValueError,OSError) as exc:raise HTTPException(409,str(exc)) from exc

    @app.delete('/api/admin/ai/model-assets/recipes/{identifier}')
    def remove_recipe(identifier:str,request:Request):
        admin(request)
        try:return models.remove_recipe(identifier)
        except (ValueError,OSError) as exc:raise HTTPException(409,str(exc)) from exc

    @app.delete('/api/admin/ai/model-assets/{identifier}')
    def remove(identifier:str,request:Request):
        admin(request)
        try:return models.remove(identifier)
        except (ValueError,OSError) as exc:raise HTTPException(409,str(exc)) from exc

    @app.get('/api/admin/ai/model-assets/{identifier}/file')
    def export(identifier:str,request:Request):
        admin(request)
        try:
            row=models.find(identifier)
            path=models._safe_path(row['_root'],row['name'],allow_hf_link=bool(models._hf_source(row['name'])))
            path=path.resolve(strict=True)
            fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
            import stat
            if not stat.S_ISREG(os.fstat(fd).st_mode):os.close(fd);raise ValueError('Not a regular model file')
            handle=os.fdopen(fd,'rb')
        except (ValueError,OSError) as exc:raise HTTPException(404,'Model file unavailable') from exc
        def chunks():
            try:
                while chunk:=handle.read(1024*1024):yield chunk
            finally:handle.close()
        from urllib.parse import quote
        return StreamingResponse(chunks(),media_type='application/octet-stream',headers={
            'Content-Disposition':"attachment; filename*=UTF-8''"+quote(Path(row['name']).name,safe=''),
            'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

    @app.post('/api/admin/ai/model-assets/{identifier}/download')
    def download(identifier:str,body:dict,request:Request):
        user=admin(request)
        if body!={'accept_licenses':True}:raise HTTPException(422,'Review the exact source and component licenses first')
        try:
            row=models.find(identifier)
            with models.mutation():pass
            if not row['source']:raise ValueError('No reviewed direct source: restore the exact file or import a complete authorized bundle')
        except (ValueError,OSError) as exc:raise HTTPException(422,str(exc)) from exc
        jid=uuid.uuid4().hex
        def run(progress,stop):
            from .storage import _atomic_json_write
            result=models.download(identifier,stop.is_set,lambda done,total:_atomic_json_write(progress,{
                'phase':'downloading-model','downloaded_bytes':done,'total_bytes':total,
                'progress_percent':round(done*100/total,1) if total else None}),job_id=jid)
            _atomic_json_write(progress,{'phase':'model-downloaded','message':'Verified source bytes downloaded; model activation and runtime admission are unchanged','result':result,'progress_percent':100})
        _,job=queue.start('studio-models','worker:studio-install',run,job_id=jid,cancellable=True,
            payload={'schema_version':1,'actor_user_id':user['id'],'model':'model-assets','file_id':identifier})
        return {'job_id':jid,'job':job}

    @app.get('/api/admin/ai/model-assets/jobs/{job_id}')
    def status(job_id:str,request:Request):
        admin(request);payload=queue.read_payload(job_id)
        if not payload or payload.get('model')!='model-assets':raise HTTPException(404,'Model transfer not found')
        return queue.get(job_id)

    @app.post('/api/admin/ai/model-assets/{identifier}/restore')
    async def restore(identifier:str,request:Request):
        admin(request)
        try:
            row=models.find(identifier);expected=row['_expected']
            if not expected or not expected.get('sha256'):raise ValueError('A reviewed SHA-256 manifest is required to restore a file')
            limit=expected.get('bytes') or 32*1024**3
            with tempfile.TemporaryDirectory(prefix='mta-model-restore-') as directory:
                target=Path(directory)/'model';count=0
                with target.open('xb') as out:
                    async for chunk in request.stream():
                        count+=len(chunk)
                        if count>limit:raise ValueError('Restored file exceeds expected size')
                        out.write(chunk)
                return models.publish(row,target,expected)
        except (ValueError,OSError) as exc:raise HTTPException(422,str(exc)) from exc
