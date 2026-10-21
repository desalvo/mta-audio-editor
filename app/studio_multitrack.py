"""Maximum mode: real Demucs separation, per-source transcription and audit.

Separation stems are not independent models and their agreement is never counted
as extra confidence. Only actual nonempty inferred parts are returned.
"""
import time
from .music_interchange import MusicResult,no_notes
from .music_reconciliation import reconcile


def transcribe_separated(user_id, audio, options, *, cancelled, timeout, progress=None, compute=None,cache=None,specialist_asset=''):
    if compute is None:
        from .studio_compute import compute
    deadline=time.monotonic()+timeout
    usage={};acknowledgements=[]

    def run(kind, plan, source, **kwargs):
        remaining=deadline-time.monotonic()
        if cancelled() or remaining<=0:
            raise RuntimeError('Separated transcription cancelled or timed out')
        execute=(lambda user,kind,plan,**args:cache.execute(compute,user,kind,plan,**args)) if cache else compute
        result,meta=execute(user_id,kind,plan,audio=source,cancelled=cancelled,
                            timeout=max(1,int(remaining)),progress=progress,**kwargs)
        if cancelled() or time.monotonic()>=deadline:
            raise RuntimeError('Separated transcription cancelled or timed out; result discarded')
        for key,value in meta.get('usage',{}).items():
            if key in ('cpu_seconds','gpu_seconds') and value is not None:
                usage[key]=usage.get(key,0)+value
        if callable(meta.get('acknowledge')):acknowledgements.append(meta['acknowledge'])
        return result

    stems=run('demucs',{'kind':'demucs','model':'htdemucs','stem_count':4},audio,artifact_mode='stems')
    parts=[];alternatives=[];warnings=[];reports={}
    for index,(filename,data) in enumerate(sorted(stems.items())):
        label=filename.removeprefix('stem_').removesuffix('.wav')
        name=str(options.get('name','Source'))[:100]+' / '+label
        primary=run('audio-to-midi-yourmt3',{'kind':'audio-to-midi-yourmt3','options':{'name':name}},data)
        # Basic Pitch explicitly does not transcribe drums. It is not run on
        # drum audio and no pitched-note output is relabeled as percussion.
        if label!='drums':
            secondary=run('audio-to-midi-basic-pitch',{'kind':'audio-to-midi-basic-pitch',
                'options':{**options,'name':name}},data)
            hypotheses=[('yourmt3',primary),('basic-pitch',secondary)]
            if specialist_asset and label=='other':
                piano=run('audio-to-midi-transkun',{'kind':'audio-to-midi-transkun','options':{'asset_id':specialist_asset,'name':name}},data)
                hypotheses.append(('transkun',piano))
            result,report=reconcile(hypotheses)
            reports[label]=report
        else:result=primary
        for part in result.parts:
            parts.append(part.model_copy(deep=True,update={'id':f's{index}-'+part.id[:60],
                                                          'name':(name+' / '+part.name)[:200]}))
        for part in result.alternatives:
            alternatives.append(part.model_copy(deep=True,update={'id':f's{index}-'+part.id[:60]}))
        warnings.extend(result.warnings)
    warnings.extend([
        'Maximum mode: Demucs htdemucs four-source separation; YourMT3 on each source, Basic Pitch on pitched sources.',
        'Stems may leak or overlap. Same-program parts retain source identity; they do not prove independent performers.',
        'No fixed instrument count or 10–16 instrument accuracy guarantee. Review duplicate notes and labels across stems.',
    ])
    from .music_channels import route_parts
    parts,routing_warnings=route_parts(parts)
    warnings.extend(routing_warnings)
    result=(MusicResult(parts=parts,alternatives=alternatives,warnings=list(dict.fromkeys(warnings))[:200])
            if parts else no_notes(list(dict.fromkeys(warnings))[:200]))

    def acknowledge():
        for callback in acknowledgements:callback()
    return result,{'usage':usage,'acknowledge':acknowledge,'separation_report':reports}
