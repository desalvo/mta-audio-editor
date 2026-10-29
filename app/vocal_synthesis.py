"""Real, deterministic CPU singing from managed CC0 diphone voicebanks.

This is concatenative synthesis, not a neural DiffSinger implementation.
English syllables or explicit phonemes/vocalises are accepted; other languages
are refused rather than silently substituted.
"""
import ctypes as C
import math
import re
from pydantic import BaseModel,ConfigDict,Field,model_validator
from .vocal_expression import Expression
from .vocal_conversion import ConversionSettings
from typing import Annotated,Literal


class Settings(BaseModel):
    model_config=ConfigDict(extra='forbid')
    backend:Literal['oddvoices','neural-external','diffsinger']='oddvoices'
    voicebank:Literal['air','cicada','quake']='air'
    voice_banks:list[Literal['air','cicada','quake']]=Field(default_factory=list,max_length=8)
    neural_bank:Annotated[str,Field(pattern=r'^$|^[a-z][a-z0-9-]{0,63}$')]=''
    neural_banks:list[Annotated[str,Field(pattern=r'^[a-z][a-z0-9-]{0,63}$')]]=Field(default_factory=list,max_length=8)
    conversion:ConversionSettings=Field(default_factory=ConversionSettings)
    language:Literal['en','it','fr','vocalise']='vocalise'
    pronunciation:Literal['native','lexicon','espeak']='native'
    expression:Expression=Field(default_factory=Expression)
    syllables:list[Annotated[str,Field(min_length=1,max_length=500)]]=Field(default_factory=list,max_length=10000)
    # Optional independent pronunciation sequences, one list per singer.
    # The legacy `syllables` field still applies to every singer when absent.
    voice_syllables:list[list[Annotated[str,Field(min_length=1,max_length=500)]]]=Field(default_factory=list,max_length=8)
    lyric_text:str=Field(default='',max_length=5000)
    melisma_counts:list[int]=Field(default_factory=list,max_length=10000)
    explicit_phones:list[list[Annotated[str,Field(pattern=r'^[^\s\x00-\x1f\x7f]{1,40}$')]]]=Field(default_factory=list,max_length=10000)
    phonemes:bool=False
    vocalise:str=Field(default='A',min_length=1,max_length=100)
    formant:float=Field(default=1,ge=.5,le=2,allow_inf_nan=False)
    articulation:float=Field(default=1,ge=.5,le=2,allow_inf_nan=False)
    gain:float=Field(default=.7,ge=0,le=1,allow_inf_nan=False)


    @model_validator(mode='after')
    def supported_features(self):
        if self.explicit_phones and (self.backend!='diffsinger' or self.pronunciation!='native' or self.lyric_text):
            raise ValueError('Explicit bank phones require DiffSinger native pronunciation without full text')
        if any(not 1<=len(row)<=64 for row in self.explicit_phones):raise ValueError('Invalid per-note phoneme sequence')
        if self.lyric_text and (self.backend!='diffsinger' or self.pronunciation!='espeak' or self.language=='vocalise'):
            raise ValueError('Automatic text alignment requires DiffSinger, eSpeak and a lyric language')
        if self.lyric_text and (self.syllables or self.voice_syllables):raise ValueError('Choose full text or note-aligned syllables, not both')
        if self.melisma_counts and not self.lyric_text:raise ValueError('Melisma counts require full lyric text')
        if self.backend!='diffsinger' and (self.neural_bank or self.neural_banks):
            raise ValueError('Managed neural banks currently use the DiffSinger backend')
        if self.backend == 'oddvoices' and self.language in ('it', 'fr'):
            raise ValueError('OddVoices supports English/vocalise; use DiffSinger for IT/FR')
        if self.backend in ('diffsinger','neural-external') and self.voice_banks:
            raise ValueError('Independent CC0 bank selections apply to OddVoices; neural singers use the configured experiment')
        if self.backend in ('diffsinger','neural-external') and (self.formant!=1 or self.articulation!=1):
            raise ValueError('Neural banks use expression gender/speed controls; OddVoices formant/articulation do not apply')
        if self.backend != 'diffsinger' and self.pronunciation != 'native':
            raise ValueError('Bank lexicon/G2P profiles require DiffSinger')
        if self.backend == 'oddvoices' and self.expression != Expression():
            raise ValueError('Score expression controls currently require DiffSinger or neural-external')
        import json
        if len(json.dumps(self.model_dump(),ensure_ascii=True).encode())>240*1024:
            raise ValueError('Vocal settings exceed the 240 KiB metadata budget; use a shorter phrase region')
        return self


def library():
    from .cpp_audio import runtime
    lib=runtime().lib
    lib.mta_vocal_abi.restype=C.c_uint
    if lib.mta_vocal_abi()!=1:raise RuntimeError('Unsupported singing ABI')
    lib.mta_vocal_open.argtypes=[C.c_char_p,C.c_char_p];lib.mta_vocal_open.restype=C.c_void_p
    lib.mta_vocal_close.argtypes=[C.c_void_p]
    lib.mta_vocal_note.argtypes=[C.c_void_p,C.c_char_p,C.c_int,C.c_double,C.c_double,C.c_uint,C.c_float,C.c_float,C.POINTER(C.c_float),C.c_uint]
    lib.mta_vocal_note.restype=C.c_int
    return lib


class Singer:
    def __init__(self,bank,dictionary):
        self.lib=library();self.handle=self.lib.mta_vocal_open(str(bank).encode('utf-8'),str(dictionary).encode('utf-8'))
        if not self.handle:raise RuntimeError('Cannot load reviewed voicebank')
    def note(self,text,phonemes,pitch,duration,cfg,rate=48000):
        import numpy as np
        if not isinstance(text,str) or not re.fullmatch(r'[A-Za-z{}@`_ .\-]+',text) or len(text)>500:raise ValueError('Use English syllables or supported X-SAMPA phonemes')
        if not 0<duration<=30:raise ValueError('Sung notes must last at most 30 seconds; split or tie long notes explicitly')
        count=math.ceil((duration+.2)*rate);pcm=np.empty(count,dtype=np.float32)
        code=self.lib.mta_vocal_note(self.handle,text.encode(),int(phonemes),440*2**((pitch-69)/12),duration,rate,cfg.formant,cfg.articulation,pcm.ctypes.data_as(C.POINTER(C.c_float)),count)
        if code==-5:raise ValueError('Assign exactly one syllable (one vowel nucleus) per note; edit the syllable or explicit phonemes')
        if code:raise ValueError('Unsupported pronunciation or voicebank render error: '+str(code))
        if not np.isfinite(pcm).all():raise ValueError('Singing renderer produced invalid audio')
        return pcm*cfg.gain
    def close(self):
        if self.handle:self.lib.mta_vocal_close(self.handle);self.handle=None


def self_test(bank,dictionary):
    import numpy as np
    singer=Singer(bank,dictionary)
    try:
        audio=singer.note('A',True,60,.5,Settings())
        if np.max(np.abs(audio))<.001:raise RuntimeError('Voicebank failed actual singing audio self-test')
        return {'frames':len(audio),'sample_rate':48000,'peak':float(np.max(np.abs(audio)))}
    finally:singer.close()


def ordered_voice_events(part, syllables):
    """Keep each lyric attached to its originating note when sorting by time."""
    events = sorted(enumerate(part.notes), key=lambda pair: (pair[1].start_ms, pair[1].pitch, pair[0]))
    if not events:
        raise ValueError('Singing requires a melody for every part')
    notes = [note for _, note in events]
    if len(notes) > 20000:
        raise ValueError('Too many notes in a single vocal part')
    for note in notes:
        if (not all(math.isfinite(float(v)) for v in (note.start_ms, note.duration_ms, note.pitch, getattr(note, "velocity", 96)))
                or note.start_ms < 0 or not 0 < note.duration_ms <= 30000
                or not 0 <= note.pitch <= 127 or not 0 <= getattr(note, "velocity", 96) <= 127):
            raise ValueError('Invalid vocal note timing, pitch or velocity')
    if any(next_note.start_ms < note.start_ms + note.duration_ms - .01
           for note, next_note in zip(notes, notes[1:])):
        raise ValueError('Each singer needs a monophonic melody; split polyphonic MIDI into parts')
    if max(note.start_ms + note.duration_ms for note in notes) > 600000:
        raise ValueError('Singing worker accepts regions up to ten minutes')
    return [(note, syllables[index] if syllables else None) for index, note in events]


def validate_voice_lyrics(parts, cfg):
    """Validate every singer's timeline and lyric alignment before loading assets."""
    if len(parts) > 8:
        raise ValueError('At most eight vocal parts per worker')
    if cfg.neural_banks and len(cfg.neural_banks)!=len(parts):
        raise ValueError('Provide exactly one neural bank per singer')
    if cfg.voice_banks and len(cfg.voice_banks) != len(parts):
        raise ValueError('Provide exactly one voicebank selection per singer')
    if cfg.voice_syllables and len(cfg.voice_syllables) != len(parts):
        raise ValueError('Provide exactly one independent syllable sequence per singer')
    import json
    if len(json.dumps(cfg.model_dump(),ensure_ascii=True).encode())>240*1024:
        raise ValueError('Vocal settings and lyrics exceed the 240 KiB metadata budget; use a shorter phrase region')
    total_notes = sum(len(part.notes) for part in parts)
    if total_notes > 40000:
        raise ValueError('Vocal Studio job exceeds the aggregate 40000-note safety budget')
    for index, part in enumerate(parts):
        syllables = cfg.voice_syllables[index] if cfg.voice_syllables else cfg.syllables
        if cfg.language != 'vocalise' and not cfg.lyric_text and len(syllables) != len(part.notes):
            raise ValueError('Assign exactly one English syllable or phoneme group to each note and singer; use repeated vowels for melismas')
        ordered_voice_events(part, syllables if cfg.language != 'vocalise' else [])


def render(score,settings,output,progress=lambda phase,message:None):
    cfg=Settings.model_validate(settings)
    from .model_license_policy import evaluate
    evaluate('vocal-synthesis', {'settings':cfg.model_dump()})
    from .vocal_banks import bank
    from .music_interchange import MusicResult
    import numpy as np
    import soundfile as sf
    validate_voice_lyrics(score.music.parts,cfg)
    if cfg.backend in ('neural-external','diffsinger'):
        from .neural_vocal_adapter import render_neural
        return render_neural(score,cfg,output,progress)
    artifacts=[]
    used_banks=[]
    for index,part in enumerate(score.music.parts):
        selected_bank=cfg.voice_banks[index] if cfg.voice_banks else cfg.voicebank
        target,dictionary=bank(selected_bank)
        singer=Singer(target,dictionary)
        try:
            syllables=cfg.voice_syllables[index] if cfg.voice_syllables else cfg.syllables
            events=ordered_voice_events(part,syllables if cfg.language=='en' else [])
            end=max(note.start_ms+note.duration_ms for note,_ in events)
            pcm=np.zeros(math.ceil((end+300)*48),dtype=np.float32)
            for j,(note,lyric) in enumerate(events):
                progress('singing',f'Voice {index+1}/{len(score.music.parts)}: note {j+1}/{len(events)}')
                text=cfg.vocalise if cfg.language=='vocalise' else lyric
                fragment=singer.note(text,cfg.phonemes or cfg.language=='vocalise',note.pitch,note.duration_ms/1000,cfg)
                offset=round(note.start_ms*48);pcm[offset:offset+len(fragment)]+=fragment*(note.velocity/127)
            peak=float(np.max(np.abs(pcm)))
            if peak>1:pcm/=peak
            path=output/f'voice-{index}.wav';sf.write(path,pcm,48000,subtype='PCM_24')
            from .vocal_conversion import convert
            conversion=convert(path,cfg.conversion.model_dump(),progress)
            artifacts.append((path,'audio/wav'))
            from .vocal_banks import digest
            used_banks.append({'name':selected_bank,'sha256':digest(target),'conversion':conversion})
        finally:
            singer.close()
    result=MusicResult(parts=score.music.parts,offset_ms=score.music.offset_ms,warnings=score.music.warnings+[
        'OddVoices concatenative CPU synthesis; English/vocalises only. One syllable per note; independent note articulation.',
        'CC0 voicebanks; no neural voice conversion or calibrated language support beyond English.'])
    path=output/'music.json';path.write_text(result.model_dump_json());artifacts.append((path,'application/json'))
    import json
    from .vocal_banks import manifest
    path=output/'singing.json';path.write_text(json.dumps({'backend':'oddvoices-concatenative','source_commit':manifest()['commit'],
        'voicebank':cfg.voicebank,'bank_sha256':used_banks[0]['sha256'] if len(used_banks)==1 else None,'voice_banks':used_banks,'settings':cfg.model_dump(),'voice_license':'CC0-1.0'}));artifacts.append((path,'application/json'))
    return artifacts
