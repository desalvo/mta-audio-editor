"""Operator-reviewed model rights and billing admission, independent of metering.

Cost recovery is not automatically NonCommercial. Acknowledgement records the
operator's decision; it does not grant rights or override the original terms.
"""
from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from dataclasses import dataclass, asdict
import hashlib
import json
import time

FREE_ADMISSION=ContextVar('mta_license_free_admission',default=False)

RESTRICTED_MODELS = frozenset({'madmom','chordformer','audio-separator-weights','uvr-kara-2','drumsep-weights',
    'diffsinger-qixuan','diffsinger-nishiren','diffsinger-spore','diffsinger-vocoder','seed-vc-assets','rvc-assets','transkun-assets','mr-mt3-assets'})

CATALOG={
    'seed-vc-assets':('GPL-3.0 code; each acoustic/encoder/vocoder/reference asset requires individual permission','disabled','https://github.com/Plachtaa/seed-vc'),
    'rvc-assets':('RVC code and individual voice/encoder/F0 checkpoints require review','disabled','https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI'),
    'mr-mt3-assets':('MIT original MR-MT3 code/weights; Apache-2.0 T5 component; exact runtime/checkpoint require operator review','disabled','https://huggingface.co/gudgud1014/MR-MT3/tree/7bd24c3e1dc26468a6a9354c0a4f174405c9bad8'),
    'transkun-assets':('MIT code; exact checkpoint and runtime require operator review','disabled','https://github.com/Yujia-Yan/Transkun'),
    'diffsinger-vocoder':('Individual vocoder checkpoint rights require review','disabled','https://github.com/openvpi/DiffSinger/blob/main/docs/BestPractices.md'),
    'basic-pitch':('Apache-2.0','cost_recovery','https://github.com/spotify/basic-pitch/blob/main/LICENSE'),
    'yourmt3':('Apache-2.0','cost_recovery','https://huggingface.co/spaces/mimbres/YourMT3/tree/5e66c1ea173a8186e0d20432b841d3180cc015b5'),
    'oddvoices':('Apache-2.0 code / CC0-1.0 voice recordings','cost_recovery','https://gitlab.com/oddvoices/oddvoices/-/blob/33a248af8df88edf5166593bf36b7e24e7bc1f94/README.md'),
    'ace-step':('Apache-2.0','cost_recovery','https://github.com/ace-step/ACE-Step/blob/main/LICENSE'),
    'whisper':('MIT','cost_recovery','https://github.com/openai/whisper/blob/main/LICENSE'),
    'demucs':('MIT','cost_recovery','https://github.com/facebookresearch/demucs/blob/main/LICENSE'),
    'sam-audio':('SAM License (conditions apply)','cost_recovery','https://github.com/facebookresearch/sam-audio/blob/main/LICENSE'),
    'mta-analysis':('EUPL-1.2 / dependency licenses','cost_recovery','https://github.com/desalvo/mta-audio-editor'),
    'madmom':('CC-BY-NC-SA-4.0 weights; separate code license','disabled','https://github.com/CPJKU/madmom/blob/main/LICENSE'),
    'chordformer':('Checkpoint rights require review','disabled','https://github.com/mwaseemrandhawa/ChordFormer'),
    'mvsep-mega53':('MIT weights: author ZFTurbo confirmed commercial use and redistribution for Mega 53 v1.0.21; training-data rights not warranted','cost_recovery','https://github.com/ZFTurbo/Music-Source-Separation-Training/issues/245'),
    'btc-hcqt':('MIT code and weights, with upstream attribution','cost_recovery','https://github.com/marcusfkelley/btc-hcqt/blob/main/LICENSE'),
    'uvr-kara-2':('UVR upstream MIT model statement; exact checkpoint commercial rights not independently confirmed','disabled','https://github.com/Anjok07/ultimatevocalremovergui/blob/master/README.md'),
    'audio-separator-weights':('Selected checkpoint rights require review','disabled','https://github.com/Anjok07/ultimatevocalremovergui'),
    'drumsep-weights':('Selected checkpoint rights require review','disabled','https://github.com/inagoy/drumsep'),
    'diffsinger-qixuan':('Custom terms: free service, complete bank, attribution','disabled','https://github.com/yqzhishen/qixuan-diffsinger/blob/main/terms_of_use/Terms_of_Use.zh-CN.md'),
    'diffsinger-nishiren':('Custom terms: commercial use requires individual approval','disabled','https://github.com/Gardanana/Nishiren-AI-Diffsinger/blob/main/terms-of-service.md'),
    'diffsinger-spore':('Modified CC-BY-NC-ND-4.0; redistribution restrictions','disabled','https://github.com/knoxstation/SPORE'),
}


class LicenseDenied(ValueError):pass


@dataclass(frozen=True)
class Decision:
    model_id:str
    mode:str
    source:str
    policy_sha256:str
    operator_review:bool=False

    @property
    def billable(self):return self.mode=='cost_recovery'


def _path():
    from .studio_catalog import root
    return root()/'license-policy.json'


def commercial_service_enabled():
    """Fail closed if the administrator's global commercial-service setting is damaged."""
    path=_path().with_name('commercial-service.json')
    if path.is_symlink() or (path.exists() and path.stat().st_size>16384):
        raise LicenseDenied('Unsafe commercial service policy')
    data=json.loads(path.read_text()) if path.is_file() else {'enabled':True}
    if not isinstance(data,dict) or type(data.get('enabled')) is not bool:
        raise LicenseDenied('Invalid commercial service policy')
    return data['enabled']


def configure_commercial_service(body,actor_id):
    """Guard model admission when commercial services are disabled.

    This is NOT a global shutdown of unrelated subscriptions or invoices.
    Operators must separately disable those services for genuinely NC use.
    """
    from .storage import _atomic_json_write
    from .ai_project_lock import project_publication_lock
    if not isinstance(body,dict) or set(body)!={'enabled','acknowledge_impact','confirm_risk_twice','reason'} or any(type(body[k]) is not bool for k in ('enabled','acknowledge_impact','confirm_risk_twice')) or body['acknowledge_impact'] is not True or body['confirm_risk_twice'] is not True or not isinstance(body['reason'],str) or not 12<=len(body['reason'])<=2000:
        raise ValueError('Explicit double confirmation and a documented reason are required')
    with project_publication_lock('studio-model:commercial-service'):
        prior=commercial_service_enabled()
        path=_path().with_name('commercial-service.json')
        record={'enabled':body['enabled'],'actor_id':actor_id,'changed_at':int(time.time()),'reason':body['reason'],'previous':prior}
        _atomic_json_write(path,record)
    return {'enabled':body['enabled'],'billing_disabled':not body['enabled']}


def overrides():
    path=_path()
    if path.is_symlink() or (path.exists() and path.stat().st_size>128*1024):raise LicenseDenied('Unsafe license policy')
    value=json.loads(path.read_text()) if path.is_file() else {}
    if not isinstance(value,dict):raise LicenseDenied('Invalid license policy')
    return value


def effective_backing_model(plan):
    """Prefer the operator's UVR default; select licensed Mega 53 only if blocked.

    Explicit engine requests never silently switch; license checks still apply
    to the final selected model at admission.
    """
    import os
    requested=plan.get('model')
    if requested:
        return requested
    preferred=os.getenv('MTA_LEAD_BACKING_DEFAULT_MODEL','uvr_mdxnet_kara_2')
    if preferred != 'uvr_mdxnet_kara_2':
        return preferred
    try:
        evaluate_model('uvr-kara-2')
    except LicenseDenied:
        # A different model with explicit MIT checkpoint evidence; its own
        # admission still fails closed if subsequently disabled by operator.
        return 'mvsep-mega53'
    return preferred


def selected(kind,plan):
    if kind=='audio-to-midi-transkun':
        from .studio_asset_registry import manifest
        value=manifest(plan.get('options',{}).get('asset_id',''))
        if value['kind']!='transkun':raise ValueError('Wrong piano model asset')
        return 'transkun-assets'
    if kind.startswith('audio-to-midi'):
        import os
        if kind.endswith('-mr-mt3') or (kind=='audio-to-midi' and os.getenv('MTA_STUDIO_TRANSCRIBER')=='mr-mt3'):return 'mr-mt3-assets'
        return 'yourmt3' if kind.endswith('-yourmt3') or (kind=='audio-to-midi' and os.getenv('MTA_STUDIO_TRANSCRIBER')=='yourmt3') else 'basic-pitch'
    if kind=='vocal-synthesis':
        if plan.get('settings',{}).get('backend','oddvoices') in ('neural-external','diffsinger'):
            import os
            settings=plan.get('settings',{})
            asset_id=settings.get('neural_bank') or next(iter(settings.get('neural_banks',[])),None)
            if asset_id:
                from .studio_asset_registry import manifest
                return manifest(asset_id)['policies']['singer']
            return os.getenv('MTA_NEURAL_SINGER_POLICY_MODEL','unreviewed-neural-singer')
        return 'oddvoices'
    if kind=='vocal-harmony':return 'mta-analysis'
    if kind in ('arranger','remix','ace-step'):return 'ace-step'
    if kind=='singer-separation':return 'sam-audio'
    if kind=='backing-vocals':
        import os
        if os.getenv('MTA_LEAD_BACKING_COMMAND','').strip():
            raise LicenseDenied('Legacy lead/backing commands have no checkpoint rights contract; use a reviewed supported model integration')
        model=effective_backing_model(plan)
        return 'mta-analysis' if model=='ffmpeg-center-side' else ('mvsep-mega53' if model=='mvsep-mega53' else ('uvr-kara-2' if model=='uvr_mdxnet_kara_2' else 'audio-separator-weights'))
    if kind=='drumsep':
        model=plan.get('model')
        if model=='dsp':return 'mta-analysis'
        if model=='mvsep-mega53':return 'mvsep-mega53'
        if model in ('sam-audio-small','sam-audio-base','sam-audio-large'):return 'sam-audio'
        return 'drumsep-weights'
    if kind=='markers':return 'madmom' if 'madmom' in str(plan.get('engine','')) else 'mta-analysis'
    if kind=='chords-ml':
        from .ai_models import CHORD_DEFAULT_ENGINE
        engine=str(plan.get('engine') or CHORD_DEFAULT_ENGINE)
        if engine.startswith('madmom'):return 'madmom'
        if engine=='chordformer':return 'chordformer'
        if engine=='btc-hcqt':return 'btc-hcqt'
        return 'mta-analysis'
    return 'sam-audio' if kind=='sam-audio' else kind


def authorize_remote_execution(kind, plan):
    """Deny unreviewed remote inference before dispatch, including native routes.

    A remote server is not proof of license compliance. The requesting host
    must authorize the actual model against its current service regime.
    """
    from .service_regime import current_regime, Regime
    import os
    if os.getenv('MTA_PULL_MODEL_ATTESTATION','off')=='verified-pull-v1':
        raise LicenseDenied('Reviewed remote inference requires the authenticated pull checkpoint protocol')
    decision = evaluate(kind, plan)
    if current_regime() == Regime.COMMERCIAL:
        # No provider/model attestation is exchanged with the remote worker yet.
        # Even locally reviewed rights cannot prove the remote checkpoint identity.
        raise LicenseDenied('Remote AI inference requires authenticated model identity and rights attestation in commercial service')
    if decision.mode != 'free_only' and not commercial_service_enabled():
        raise LicenseDenied('Remote AI licensing is not approved under the current service configuration')
    return decision


def evaluate(kind,plan):
    from .model_selectors import validate_selection
    validate_selection(kind,plan)
    primary=evaluate_model(selected(kind,plan));decisions=[primary];asset_ids=[];inventories=[]
    if kind=='audio-to-midi-transkun':asset_ids.append(plan.get('options',{}).get('asset_id',''))
    if kind=='vocal-synthesis':
        settings=plan.get('settings',{})
        asset_ids=list(settings.get('neural_banks',[]))
        if settings.get('neural_bank'):asset_ids.append(settings['neural_bank'])
        conversion=settings.get('conversion',{}).get('asset_id')
        if conversion:asset_ids.append(conversion)
        if settings.get('backend')=='diffsinger' and not (settings.get('neural_bank') or settings.get('neural_banks')):
            import os
            decisions.append(evaluate_model(os.getenv('MTA_DIFFSINGER_VOCODER_POLICY_MODEL','diffsinger-vocoder')))
    if asset_ids:
        from .studio_asset_registry import manifest
        for asset_id in sorted(set(asset_ids)):
            value=manifest(asset_id,verify=True)
            if not value['enabled']:raise LicenseDenied('Managed model asset is disabled')
            decisions.extend(evaluate_model(notice['policy_model']) for notice in value['licenses'])
            # Portable identity: bind bytes, component permissions and runtime
            # bindings, never an installation path or a mutable enabled flag.
            inventories.append({k:v for k,v in value.items() if k not in ('folder','enabled')})
    if len(decisions)==1:return primary
    material=(''.join(d.policy_sha256 for d in decisions) if not inventories else
              json.dumps({'schema':'mta-managed-execution-1',
                          'policies':[asdict(d) for d in decisions],
                          'assets':inventories},sort_keys=True,separators=(',',':'),allow_nan=False))
    digest=hashlib.sha256(material.encode()).hexdigest()
    return Decision(primary.model_id,'free_only' if any(not d.billable for d in decisions) else 'cost_recovery',
                    primary.source,digest,any(d.operator_review for d in decisions))


def evaluate_singing_components():
    """Both installed component permissions are required by direct child CLIs.

    An operator's acoustic policy never grants rights to a separate vocoder.
    No request field or inherited admission envelope can substitute these IDs.
    """
    import os
    return [evaluate_model(os.getenv('MTA_NEURAL_SINGER_POLICY_MODEL','unreviewed-neural-singer')),
            evaluate_model(os.getenv('MTA_DIFFSINGER_VOCODER_POLICY_MODEL','diffsinger-vocoder'))]


def evaluate_model(model_id):
    known=CATALOG.get(model_id,('Unreviewed model/weights','disabled',''))
    custom=overrides().get(model_id,{})
    mode=custom.get('mode',known[1])
    if mode not in ('disabled','free_only','cost_recovery'):raise LicenseDenied('Invalid model licensing mode')
    # Re-evaluate rights at the admission boundary, including policy files
    # imported/restored without passing through the administrative writer.
    if model_id == 'diffsinger-qixuan' and mode == 'cost_recovery':
        raise LicenseDenied('Qixuan cannot be enabled for paid inference')
    if custom.get('authorization_basis') == 'noncommercial_context' and mode != 'disabled':
        if mode != 'free_only':
            raise LicenseDenied('Noncommercial-context authorization cannot be billed')
        from .service_regime import current_regime, Regime
        if current_regime() == Regime.COMMERCIAL:
            raise LicenseDenied('Noncommercial-context authorization is incompatible with commercial service')
    if mode=='cost_recovery' and not commercial_service_enabled():
        raise LicenseDenied('Commercial service is globally disabled; this model must have a reviewed free-only authorization')
    # Enforce the active service regime at the model admission boundary, not
    # merely in the model picker. The commercial regime may not run a free-only
    # model absent a separately reviewed commercial authorization recorded as
    # cost_recovery in the version-specific operator policy.
    from .service_regime import current_regime, Regime
    if current_regime() == Regime.COMMERCIAL and mode == 'free_only':
        raise LicenseDenied('Free-only model is not authorized for the commercial service: '+model_id)
    if mode=='disabled':raise LicenseDenied('Model disabled pending license review: '+model_id+'. Contact the administrator; cost recovery alone does not grant permission.')
    source=custom.get('evidence_url') or known[2]
    fingerprint=hashlib.sha256(json.dumps({'model':model_id,'license':known[0],'policy':custom,'source':source},sort_keys=True).encode()).hexdigest()
    return Decision(model_id,mode,source,fingerprint,bool(custom))


@contextmanager
def admission(decision):
    token=FREE_ADMISSION.set(isinstance(decision,Decision) and decision.mode=='free_only')
    try:yield
    finally:FREE_ADMISSION.reset(token)


def configure(model_id,body,actor_id):
    from urllib.parse import urlsplit
    from .storage import _atomic_json_write
    from .ai_project_lock import project_publication_lock
    if model_id not in descriptors():raise ValueError('Unknown registered model')
    if (not isinstance(body,dict) or not {'mode','acknowledge_responsibility','evidence_url','reason','free_access_confirmed'} <= set(body)
            or set(body)-{'mode','acknowledge_responsibility','evidence_url','reason','free_access_confirmed','authorization_basis','confirm_risk_twice'}
            or body['mode'] not in ('disabled','free_only','cost_recovery') or body['acknowledge_responsibility'] is not True
            or type(body['free_access_confirmed']) is not bool or not isinstance(body['reason'],str) or not 12<=len(body['reason'])<=2000
            or not isinstance(body['evidence_url'],str) or len(body['evidence_url'])>2000):
        raise ValueError('Choose a mode, state the reviewed permission and explicitly accept operator responsibility')
    if body['mode']!='disabled':
        if model_id=='diffsinger-qixuan' and body['mode']!='free_only':raise ValueError('Published Qixuan terms prohibit paid inference services, including cost recovery; free-only mode is required')
        if model_id in RESTRICTED_MODELS or model_id not in CATALOG:
            if body.get('confirm_risk_twice') is not True:
                raise ValueError('Restricted model activation requires a second explicit confirmation')
            if body.get('authorization_basis') not in ('written_permission','verified_license','noncommercial_context'):
                raise ValueError('Document an actual authorization basis; operator responsibility alone is insufficient')
            if model_id in ('chordformer','audio-separator-weights','uvr-kara-2','drumsep-weights') and body['authorization_basis']=='noncommercial_context':
                raise ValueError('Unknown checkpoint permissions cannot be cured by selecting noncommercial mode')
            if body['authorization_basis']=='noncommercial_context' and commercial_service_enabled():
                raise ValueError('Disable the entire commercial service before using a NonCommercial-only permission')
            if body['authorization_basis']=='noncommercial_context' and body['mode']!='free_only':
                raise ValueError('Noncommercial-context activation cannot be billed')
        parsed=urlsplit(body['evidence_url'])
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password:raise ValueError('Provide an HTTPS license/permission reference without credentials')
        if body['mode']=='cost_recovery' and not commercial_service_enabled():
            raise ValueError('Cannot activate paid inference when commercial service is disabled')
        if body['mode']=='free_only' and not body['free_access_confirmed']:raise ValueError('Free-only models require access without subscription, credits or model-related storage charges')
        if model_id=='diffsinger-qixuan' and body['mode']!='free_only':raise ValueError('Published Qixuan terms prohibit paid inference services, including cost recovery; free-only mode is required')
    with project_publication_lock('studio-model:license-policy'):
        values=overrides()
        prior=values.get(model_id)
        entry={**body,'actor_id':actor_id,'reviewed_at':int(time.time())}
        # Preserve previous operator attestations, even when a later reviewer
        # changes the mode. Avoid silently replacing the supporting evidence.
        history_path=_path().with_name('license-policy-history.json')
        if history_path.is_symlink() or (history_path.exists() and history_path.stat().st_size>2*1024*1024):
            raise LicenseDenied('Unsafe license policy history')
        history=json.loads(history_path.read_text()) if history_path.is_file() else []
        if not isinstance(history,list) or len(history)>4096:raise LicenseDenied('Invalid license policy history')
        history.append({'model_id':model_id,'previous':prior,'review':entry})
        _atomic_json_write(history_path,history)
        values[model_id]=entry
        _atomic_json_write(_path(),values)
    return catalog()


def catalog():
    """Present effective regime admission, not merely the operator's selected mode.

    This catalog must not offer an enabled model that the server rejects. Errors
    reading regime/rights policy are represented as unavailable (fail closed).
    """
    from .model_rights_dossiers import DOSSIERS
    custom=overrides()
    items=[]
    for name,(license_name,default,source) in descriptors().items():
        selected_mode=custom.get(name,{}).get('mode',default)
        try:
            decision=evaluate_model(name)
            available=True
            effective_mode=decision.mode
            denial=None
        except (LicenseDenied, ValueError, OSError) as exc:
            available=False
            effective_mode='disabled'
            denial=str(exc)
        items.append({'id':name,'license':license_name,'default_mode':default,
             'mode':selected_mode,'effective_mode':effective_mode,
             'available_in_current_regime':available,'license_denial_reason':denial,
             'license_url':source,'operator_review':custom.get(name),
             'manual_activation_does_not_grant_rights':True,'rights_dossier':DOSSIERS.get(name),
             'requires_second_confirmation':name in RESTRICTED_MODELS or name not in CATALOG})
    return items

def descriptors():
    from .ai_worker_registry import extensions
    from .studio_asset_registry import catalog as asset_catalog
    registered={n['policy_model']:('Operator-registered asset: independent rights review required','disabled',n['evidence_url'])
                for asset in asset_catalog() for n in asset.get('licenses',[])}
    return {**registered,**{name:('Operator-registered engine: code and checkpoint rights require review','disabled','')
               for name in extensions()},**CATALOG}


def record_job(job_id,decision,*,_connection=None):
    from .ai_billing import db
    with (db() if _connection is None else nullcontext(_connection)) as con:
        con.execute('''CREATE TABLE IF NOT EXISTS ai_job_license_snapshots(
            job_id TEXT PRIMARY KEY REFERENCES ai_compute_jobs(id) ON DELETE CASCADE,
            model_id TEXT NOT NULL,mode TEXT NOT NULL,policy_json TEXT NOT NULL)''')
        document=json.dumps(asdict(decision),sort_keys=True)
        previous=con.execute('SELECT policy_json FROM ai_job_license_snapshots WHERE job_id=?',(job_id,)).fetchone()
        if previous:
            if previous[0]!=document:raise LicenseDenied('Job license decision changed; submit a new job')
            return
        con.execute('INSERT INTO ai_job_license_snapshots VALUES(?,?,?,?)',
                    (job_id,decision.model_id,decision.mode,document))
