"""Administrator model actions use fixed recipes and the existing job queue."""
import uuid
from fastapi import HTTPException,Request
from . import ai_arranger_runtime as queue
from . import studio_catalog as catalog


def register_routes(app,actor):
    def admin(request):
        import os
        if request.url.path.startswith('/api/native/') and os.getenv('MTA_NATIVE_SINGLE_USER','').lower()!='true':raise HTTPException(404,'Native model settings unavailable')
        user=actor(request)
        if user['role']!='admin':raise HTTPException(403,'Administrator required')
        return user

    @app.post('/api/native/ai/studio/assets/install')
    @app.post('/api/admin/ai/studio/assets/install')
    async def install_managed(request:Request,accept_licenses:bool=False):
        user=admin(request)
        if not accept_licenses:raise HTTPException(422,'Explicit component-license review is required')
        import os
        from .studio_asset_registry import root,MAX_BUNDLE,install
        path=root()/('.incoming-'+uuid.uuid4().hex+'.zip');count=0
        try:
            with path.open('xb') as out:
                async for chunk in request.stream():
                    count+=len(chunk)
                    if count>MAX_BUNDLE:raise HTTPException(413,'Model archive exceeds 4 GiB')
                    out.write(chunk)
                out.flush();os.fsync(out.fileno())
            if count==0:raise HTTPException(422,'Empty model archive')
            jid=uuid.uuid4().hex
            def run(progress,stop):
                from .storage import _atomic_json_write
                try:install(path,stop.is_set,lambda phase,done,total:_atomic_json_write(progress,{
                    'phase':phase,'completed_units':done,'total_units':total,'progress_percent':round(done*100/total,1) if total else None}))
                finally:path.unlink(missing_ok=True)
            _,job=queue.start('studio-models','worker:studio-install',run,job_id=jid,cancellable=True,
                payload={'schema_version':1,'actor_user_id':user['id'],'model':'managed-bundle'})
            return {'job_id':jid,'job':job}
        except BaseException:
            path.unlink(missing_ok=True);raise

    @app.put('/api/native/ai/studio/assets/{asset_id}')
    @app.put('/api/admin/ai/studio/assets/{asset_id}')
    def configure_managed(asset_id:str,body:dict,request:Request):
        admin(request)
        if set(body)!={'enabled'}:raise HTTPException(422,'Expected enabled boolean')
        from .studio_asset_registry import configure
        try:return configure(asset_id,body['enabled'])
        except (ValueError,OSError) as exc:raise HTTPException(422,str(exc)) from exc

    @app.delete('/api/native/ai/studio/assets/{asset_id}')
    @app.delete('/api/admin/ai/studio/assets/{asset_id}')
    def remove_managed(asset_id:str,request:Request):
        admin(request)
        from .studio_asset_registry import remove
        try:return remove(asset_id)
        except (ValueError,OSError) as exc:raise HTTPException(409,str(exc)) from exc

    @app.get('/api/native/ai/studio/models')
    @app.get('/api/admin/ai/studio/models')
    def models(request:Request):
        admin(request)
        from .studio_jobs import studio_policy
        from .gm_instruments import status as gm_status
        from .model_license_policy import catalog as licenses,commercial_service_enabled
        from .vocal_banks import status as voices
        return {**catalog.capabilities(),'policy':studio_policy(),'gm':gm_status(),'licenses':licenses(),'commercial_service_enabled':commercial_service_enabled(),'voicebanks':voices()}

    @app.put('/api/native/ai/studio/licenses/{model_id}')
    @app.put('/api/admin/ai/studio/licenses/{model_id}')
    def model_license(model_id:str,body:dict,request:Request):
        user=admin(request)
        from .model_license_policy import configure
        try:return {'licenses':configure(model_id,body,user['id'])}
        except (ValueError,OSError) as exc:raise HTTPException(422,str(exc)) from exc

    @app.put('/api/native/ai/studio/commercial-service')
    @app.put('/api/admin/ai/studio/commercial-service')
    def commercial_service(body:dict,request:Request):
        user=admin(request)
        from .model_license_policy import configure_commercial_service
        try:return configure_commercial_service(body,user['id'])
        except (ValueError,OSError) as exc:raise HTTPException(422,str(exc)) from exc

    @app.post('/api/native/ai/studio/voicebanks/{voice}/install')
    @app.post('/api/admin/ai/studio/voicebanks/{voice}/install')
    def install_voice(voice:str,body:dict,request:Request):
        user=admin(request)
        from .vocal_banks import VOICES,install
        if voice not in VOICES:raise HTTPException(404,'Unknown reviewed voicebank')
        if body!={'accept_licenses':True}:raise HTTPException(422,'Review Apache-2.0 engine, CC0 voice and dictionary license notices before installation')
        jid=uuid.uuid4().hex
        def run(progress,stop):
            from .storage import _atomic_json_write
            install(voice,stop.is_set,lambda phase,done,total:_atomic_json_write(progress,{
                'phase':phase,'message':phase,'completed_units':done,'total_units':total,
                'progress_percent':round(done*100/total,1) if total else None}))
        _,job=queue.start('studio-models','worker:studio-install',run,job_id=jid,cancellable=True,
            payload={'schema_version':1,'actor_user_id':user['id'],'model':'oddvoices','voice':voice})
        return {'job_id':jid,'job':job}

    @app.put('/api/native/ai/studio/policy')
    @app.put('/api/admin/ai/studio/policy')
    def policy(body:dict,request:Request):
        admin(request)
        if set(body)!={'timeout_seconds','retention_days'} or any(type(v) is not int for v in body.values()) or not 60<=body['timeout_seconds']<=14400 or not 1<=body['retention_days']<=365:
            raise HTTPException(422,'Timeout must be 60–14400 seconds; retention 1–365 days')
        from .storage import _atomic_json_write
        _atomic_json_write(catalog.root()/'policy.json',body)
        return body

    @app.delete('/api/native/ai/studio/voicebanks/{voice}')
    @app.delete('/api/admin/ai/studio/voicebanks/{voice}')
    def remove_voice(voice:str,request:Request):
        admin(request)
        from .vocal_banks import uninstall
        try:return uninstall(voice)
        except (ValueError,OSError) as exc:raise HTTPException(409,str(exc)) from exc

    @app.post('/api/native/ai/studio/models/basic-pitch/install')
    @app.post('/api/admin/ai/studio/models/basic-pitch/install')
    def install(body:dict,request:Request):
        user=admin(request)
        if body!={'accept_licenses':True}:raise HTTPException(422,'Explicit review and acceptance of the linked code/model licenses required')
        job_id=uuid.uuid4().hex
        def run(progress,stop):
            from .storage import _atomic_json_write
            catalog.install_basic_pitch(stop.is_set,lambda phase:_atomic_json_write(progress,{'phase':phase,'message':phase,'progress_percent':None}))
        _,job=queue.start('studio-models','worker:studio-install',run,job_id=job_id,cancellable=True,
            payload={'schema_version':1,'actor_user_id':user['id'],'model':'basic-pitch'})
        return {'job_id':job_id,'job':job}

    @app.put('/api/native/ai/studio/models/basic-pitch')
    @app.put('/api/admin/ai/studio/models/basic-pitch')
    def configure(body:dict,request:Request):
        admin(request)
        if set(body)!={'enabled'} or type(body['enabled']) is not bool:raise HTTPException(422,'Expected enabled boolean')
        from .ai_project_lock import project_publication_lock
        from .storage import _atomic_json_write
        with project_publication_lock('studio-model:basic-pitch'):
            value=catalog.receipt()
            if not value:raise HTTPException(404,'Model not installed')
            value['enabled']=body['enabled'];value.pop('python',None);value.pop('runtime',None)
            _atomic_json_write(catalog.root()/'basic-pitch.json',value)
        return catalog.capabilities()

    @app.get('/api/native/ai/studio/installations/{job_id}')
    @app.get('/api/admin/ai/studio/installations/{job_id}')
    def installation(job_id:str,request:Request):
        admin(request);payload=queue.read_payload(job_id)
        if not payload or payload.get('model') not in ('basic-pitch','gm-pack','oddvoices','managed-bundle'):raise HTTPException(404,'Installation not found')
        return queue.get(job_id)

    @app.post('/api/native/ai/studio/models/basic-pitch/test')
    @app.post('/api/admin/ai/studio/models/basic-pitch/test')
    def quick_test(request:Request):
        user=admin(request)
        if not catalog.receipt():raise HTTPException(404,'Model not installed')
        jid=uuid.uuid4().hex
        def run(progress,stop):
            from .storage import _atomic_json_write
            catalog.test_basic_pitch(stop.is_set,lambda phase:_atomic_json_write(progress,{'phase':phase,'progress_percent':None}))
        _,job=queue.start('studio-models','worker:studio-test',run,job_id=jid,cancellable=True,
            payload={'schema_version':1,'actor_user_id':user['id'],'model':'basic-pitch'})
        return {'job_id':jid,'job':job}

    @app.delete('/api/native/ai/studio/models/basic-pitch')
    @app.delete('/api/admin/ai/studio/models/basic-pitch')
    def uninstall(request:Request):
        admin(request)
        from .ai_project_lock import project_publication_lock
        import shutil
        with project_publication_lock('studio-model:basic-pitch'):
            with queue._db() as con:
                active=con.execute("SELECT 1 FROM jobs WHERE operation IN ('worker:studio-music','worker:studio-install','worker:studio-test') AND state IN ('running','queued','blocked') LIMIT 1").fetchone()
            if active:raise HTTPException(409,'Wait for Studio jobs to finish or cancel them before uninstalling')
            value=catalog.receipt()
            if not value:raise HTTPException(404,'Model not installed')
            runtime=catalog.root()/'basic-pitch-0.4.0-onnx-v1'
            if runtime.is_symlink():raise HTTPException(409,'Unsafe runtime directory')
            (catalog.root()/'basic-pitch.json').unlink()
            shutil.rmtree(runtime)
        return catalog.capabilities()

    @app.post('/api/native/ai/studio/models/gm-pack/install')
    @app.post('/api/admin/ai/studio/models/gm-pack/install')
    def install_gm(body:dict,request:Request):
        user=admin(request)
        if body!={'accept_licenses':True}:raise HTTPException(422,'Review and accept MIT bank/engine licenses before installing')
        jid=uuid.uuid4().hex
        def run(progress,stop):
            from .gm_installer import install
            from .storage import _atomic_json_write
            install(stop.is_set,lambda phase,done,total:_atomic_json_write(progress,{'phase':phase,'message':phase,
                'downloaded_bytes':done,'total_bytes':total,'progress_percent':round(done*100/total,1) if total else None}))
        _,job=queue.start('studio-models','worker:studio-install',run,job_id=jid,cancellable=True,
            payload={'schema_version':1,'actor_user_id':user['id'],'model':'gm-pack'})
        return {'job_id':jid,'job':job}

    @app.post('/api/native/ai/studio/models/gm-pack/test')
    @app.post('/api/admin/ai/studio/models/gm-pack/test')
    def test_gm(request:Request):
        admin(request)
        from .gm_installer import self_test
        try:return self_test()
        except (ValueError,RuntimeError,OSError) as exc:raise HTTPException(422,str(exc)) from exc

    @app.delete('/api/native/ai/studio/models/gm-pack')
    @app.delete('/api/admin/ai/studio/models/gm-pack')
    def uninstall_gm(request:Request):
        admin(request)
        from .gm_installer import uninstall
        try:return uninstall()
        except (ValueError,OSError) as exc:raise HTTPException(409,str(exc)) from exc
