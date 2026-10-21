"""Bounded, data-only score transport for registered studio workers."""
from pydantic import BaseModel, ConfigDict, Field
from .models import Chord, LyricLine
from .music_interchange import MusicResult


class Score(BaseModel):
    model_config = ConfigDict(extra='forbid')
    music: MusicResult
    chords: list[Chord] = Field(default_factory=list, max_length=10000)
    lyrics: list[LyricLine] = Field(default_factory=list, max_length=10000)


def validate(data):
    if not isinstance(data, bytes) or not 0 < len(data) <= 8*1024*1024:
        raise ValueError('Score document must be 1 byte to 8 MiB')
    return Score.model_validate_json(data)


MAX_STUDIO_OPTIONS=240*1024


def options_for_score(kind,options):
    """Typed score options; large lyrics/automation travel in the body, not headers."""
    import json
    if kind not in ('vocal-harmony','vocal-synthesis') or not isinstance(options,dict):
        raise ValueError('Unsupported structured Studio options')
    if set(options)-{'kind','settings'} or options.get('kind',kind)!=kind:
        raise ValueError('Unsupported structured Studio option key')
    raw=json.dumps(options,allow_nan=False,ensure_ascii=True).encode()
    if len(raw)>MAX_STUDIO_OPTIONS:raise ValueError('Studio options exceed 240 KiB')
    if kind=='vocal-synthesis':
        from .vocal_synthesis import Settings
        Settings.model_validate(options.get('settings',{}))
    else:
        from .vocal_harmony import HarmonySettings
        HarmonySettings.model_validate(options.get('settings',{}))
    return options


def pack_request(score,kind,options):
    import json
    validate(score);options_for_score(kind,options)
    body=json.dumps({'schema':'mta-studio-request-1','score':json.loads(score),'options':options},
                    allow_nan=False,separators=(',',':')).encode()
    if len(body)>8*1024*1024:raise ValueError('Structured Studio request exceeds 8 MiB')
    return body


def unpack_request(body,kind):
    import json
    from .ai_remote_transport import _unique_pairs
    if not isinstance(body,bytes) or not 0<len(body)<=8*1024*1024:raise ValueError('Invalid Studio request size')
    try:value=json.loads(body,object_pairs_hook=_unique_pairs)
    except (UnicodeError,json.JSONDecodeError,RecursionError) as exc:raise ValueError('Invalid Studio request JSON') from exc
    if not isinstance(value,dict) or set(value)!={'schema','score','options'} or value['schema']!='mta-studio-request-1':
        raise ValueError('Invalid Studio request envelope')
    options=options_for_score(kind,value['options'])
    score=json.dumps(value['score'],allow_nan=False,separators=(',',':')).encode()
    validate(score)
    return score,options
