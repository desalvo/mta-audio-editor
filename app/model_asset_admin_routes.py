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

    def lifecycle_job(user, action, run):
        jid = uuid.uuid4().hex
        def execute(progress, stop):
            from .storage import _atomic_json_write
            _atomic_json_write(progress, {'phase':action, 'message':action})
            result = run(jid, stop.is_set)
            _atomic_json_write(progress, {'phase':action, 'message':'Completed',
                                          'progress_percent':100, 'result':result})
        _, job = queue.start('studio-models', 'worker:studio-install', execute, job_id=jid,
            payload={'schema_version':1, 'actor_user_id':user['id'], 'model':'model-assets', 'action':action})
        return {'job_id':jid, 'job':job}

    @app.post('/api/admin/ai/model-assets/runtime/install')
    def install_audio_runtime(body:dict, request:Request):
        user = admin(request)
        from . import ai_runtime_admin
        if set(body) != {'accept_licenses', 'device'} or body['accept_licenses'] is not True or body['device'] not in ('auto','cpu','cuda','rocm'):
            raise HTTPException(422, 'Explicit license acceptance and a supported device are required')
        if not ai_runtime_admin.status()['can_install']:
            raise HTTPException(409, 'The local server cannot provision this runtime')
        return lifecycle_job(user, 'install-audio-runtime',
            lambda jid, cancelled: ai_runtime_admin.install(body['device'], cancelled, jid))

    @app.post('/api/admin/ai/model-assets/runtime/remove')
    def remove_audio_runtime(request:Request):
        user = admin(request)
        from . import ai_runtime_admin
        if not ai_runtime_admin.status()['can_remove']:
            raise HTTPException(409, 'The local server cannot remove this runtime')
        return lifecycle_job(user, 'remove-audio-runtime', lambda jid, _: ai_runtime_admin.remove(jid))

    @app.post('/api/admin/ai/model-assets/recipes/{identifier}/remove')
    def remove_recipe_job(identifier:str, request:Request):
        user = admin(request)
        if not any(row['id'] == identifier and row.get('remove_job_url') for row in models.recipes()):
            raise HTTPException(404, 'Unknown managed model removal recipe')
        return lifecycle_job(user, 'remove-model', lambda jid, _: models.remove_recipe(identifier, jid))

    @app.post('/api/admin/ai/mega53/runtime/remove')
    def remove_mega53_runtime(request:Request):
        user = admin(request)
        from . import mega53_install
        return lifecycle_job(user, 'remove-mega53-runtime', lambda jid, _: mega53_install.remove(checkpoint=False, job_id=jid))

    @app.post('/api/admin/ai/mega53/weights/install')
    def install_mega53_weights(body:dict, request:Request):
        user = admin(request)
        if body != {'accept_licenses':True}:
            raise HTTPException(422, 'Review the exact component licenses first')
        from . import mega53_install
        return lifecycle_job(user, 'install-mega53-checkpoint', lambda jid, cancelled: mega53_install.install_checkpoint(cancelled, jid))

    @app.post('/api/admin/ai/mega53/weights/remove')
    def remove_mega53_weights(request:Request):
        user = admin(request)
        from . import mega53_install
        return lifecycle_job(user, 'remove-mega53-checkpoint', lambda jid, _: mega53_install.remove(checkpoint=True, job_id=jid))

    @app.post('/api/admin/ai/mega53/runtime/install')
    def install_mega53_runtime(body:dict,request:Request):
        user=admin(request)
        if set(body)!={'accept_licenses','device'} or body.get('accept_licenses') is not True or body.get('device') not in ('auto','cpu','cuda','rocm'):
            raise HTTPException(422,'Explicit license acceptance and a supported device are required')
        jid=uuid.uuid4().hex
        def run(progress,stop):
            from . import mega53_install
            from .storage import _atomic_json_write
            def update(phase,done,total):
                _atomic_json_write(progress,{'phase':phase,'message':phase,'downloaded_bytes':done,
                    'total_bytes':total,'progress_percent':round(done*100/total,1) if total else None})
            result=mega53_install.install(body['device'],stop.is_set,update,job_id=jid)
            _atomic_json_write(progress,{'phase':'mega53-installed','message':'Checkpoint and strict model load verified; real inference remains untested',
                'progress_percent':100,'result':result})
        _,job=queue.start('studio-models','worker:studio-install',run,job_id=jid,cancellable=True,
            payload={'schema_version':1,'actor_user_id':user['id'],'model':'mega53-runtime'})
        return {'job_id':jid,'job':job}

    @app.get('/api/admin/ai/mega53/runtime/installations/{job_id}')
    def mega53_installation_status(job_id:str,request:Request):
        admin(request)
        payload=queue.read_payload(job_id)
        if not payload or payload.get('model')!='mega53-runtime':raise HTTPException(404,'Mega 53 installation not found')
        return queue.get(job_id)

    @app.post('/api/admin/ai/mega53/checkpoint/verify')
    def verify_mega53(request:Request):
        admin(request)
        from . import mega53_runtime as mega
        try:
            mega.verify_mega53_checkpoint(mega._required_setting('MTA_MEGA53_CHECKPOINT'))
            try:
                mega.check_local_configuration()
                paths_ready = True
            except (RuntimeError, OSError):
                paths_ready = False
            return {'checkpoint_verified':True,'paths_ready':paths_ready,
                    'inference_tested':False,'scope':'local-server'}
        except (RuntimeError, OSError) as exc:
            raise HTTPException(409,str(exc)) from exc

    @app.post('/api/admin/ai/mega53/checkpoint/install')
    async def install_mega53(request:Request,accept_licenses:bool=False):
        admin(request)
        if not accept_licenses:raise HTTPException(422,'Review the exact component licenses first')
        from . import mega53_runtime as mega
        destination=mega.managed_checkpoint()
        try:
            if os.getenv('MTA_MEGA53_CHECKPOINT'):
                raise ValueError('An external checkpoint override is configured; remove it before installing the managed checkpoint')
            root=destination.parent
            if root.is_symlink() or root.parent.is_symlink():raise ValueError('Unsafe managed model directory')
            root.mkdir(parents=True,exist_ok=True)
            if destination.is_symlink():raise ValueError('Unsafe managed checkpoint')
            with tempfile.TemporaryDirectory(prefix='.mega53-',dir=root) as folder:
                staged=Path(folder)/'checkpoint';size=0
                with staged.open('xb') as stream:
                    async for chunk in request.stream():
                        size+=len(chunk)
                        if size>8*1024**3:raise ValueError('Checkpoint exceeds the maximum upload size')
                        stream.write(chunk)
                mega.verify_mega53_checkpoint(staged)
                with models.mutation():
                    if destination.is_symlink():raise ValueError('Unsafe managed checkpoint')
                    os.replace(staged,destination)
            try:
                mega.check_local_configuration()
                paths_ready=True
            except (RuntimeError,OSError):
                paths_ready=False
            return {'checkpoint_verified':True,'paths_ready':paths_ready,
                    'inference_tested':False,'scope':'local-server'}
        except (ValueError,RuntimeError,OSError) as exc:raise HTTPException(409,str(exc)) from exc

    @app.get('/api/admin/ai/model-assets')
    def inventory(request:Request,engine:str='',search:str=Query('',max_length=200),offset:int=Query(0,ge=0),limit:int=Query(100,ge=1,le=250)):
        admin(request)
        from .ai_runtime_admin import status
        try:return {**models.inventory(engine,search,offset,limit),'recipes':models.recipes(),'runtime':status()}
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
