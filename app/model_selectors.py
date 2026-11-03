"""Closed model selectors; engine permission never approves an arbitrary path.

These identifiers classify requested checkpoints, not their installed byte rights.
Whisper names are pinned to the production dependency20250625; Demucs profiles
share the existing model-updater registry. No model/runtime import or network I/O.
"""
import argparse
import os

WHISPER_MODELS=frozenset({
    'tiny.en','tiny','base.en','base','small.en','small','medium.en','medium',
    'large-v1','large-v2','large-v3','large','large-v3-turbo','turbo',
})

OFFICIAL_DEMUCS_MODELS={
 "htdemucs":{"stem_count":4,"stem_labels":["drums","bass","other","vocals"]},
 "htdemucs_ft":{"stem_count":4,"stem_labels":["drums","bass","other","vocals"]},
 "htdemucs_6s":{"stem_count":6,"stem_labels":["drums","bass","other","vocals","guitar","piano"]},
 "hdemucs_mmi":{"stem_count":4,"stem_labels":["drums","bass","other","vocals"]},
 "mdx":{"stem_count":4,"stem_labels":["drums","bass","other","vocals"]},
 "mdx_extra":{"stem_count":4,"stem_labels":["drums","bass","other","vocals"]},
 "mdx_q":{"stem_count":4,"stem_labels":["drums","bass","other","vocals"]},
 "mdx_extra_q":{"stem_count":4,"stem_labels":["drums","bass","other","vocals"]},
 "repro_mdx_a":{"stem_count":4,"stem_labels":["drums","bass","other","vocals"]},
 "repro_mdx_a_hybrid_only":{"stem_count":4,"stem_labels":["drums","bass","other","vocals"]},
 "repro_mdx_a_time_only":{"stem_count":4,"stem_labels":["drums","bass","other","vocals"]},
}


def whisper_model(value=None):
    if value is None or value=='':value=os.getenv('MTA_LYRICS_WHISPER_MODEL','turbo')
    if not isinstance(value,str):raise ValueError('Whisper requires a published model identifier')
    value=value.strip() or 'turbo'
    if value not in WHISPER_MODELS:raise ValueError('Unsupported Whisper checkpoint; local paths are not model permissions')
    return value


def demucs_model(value=None):
    if value is None or value=='':value='htdemucs'
    if not isinstance(value,str) or value not in OFFICIAL_DEMUCS_MODELS:
        raise ValueError('Select a declared Demucs checkpoint; custom model names require separate review')
    return value


def validate_selection(kind,plan):
    if kind=='whisper':whisper_model(plan.get('model'))
    elif kind=='demucs':demucs_model(plan.get('model'))
    elif kind in ('sam-audio','singer-separation') or (kind=='drumsep' and str(plan.get('model','')).lower().rsplit('/',1)[-1].startswith('sam-')):
        raise ValueError('Requested separator has been removed')


def demucs_arguments(arguments):
    # The profiled child is an execution boundary too. Bind its explicit model;
    # do not let an upstream argparse abbreviation or local --repo override it.
    for argument in arguments:
        flag=argument.split('=',1)[0]
        if flag.startswith('-r') and not flag.startswith('--'):
            raise ValueError('Custom Demucs repository selector')
        if flag.startswith('--') and (('--repo'.startswith(flag))
                or ('--name'.startswith(flag) and flag!='--name')):
            raise ValueError('Ambiguous or custom Demucs repository selector')
    parser=argparse.ArgumentParser(add_help=False,allow_abbrev=False,exit_on_error=False)
    parser.add_argument('-n','--name',action='append')
    try:value,_=parser.parse_known_args(arguments)
    except argparse.ArgumentError as exc:raise ValueError('Invalid Demucs model selector') from exc
    if not value.name or len(value.name)!=1:raise ValueError('One explicit Demucs model selector required')
    return demucs_model(value.name[0])
