"""Bounded score expression. F0 is score automation, never learned prediction."""
import math
import bisect
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

PRESETS = {
    'neutral': {},
    'gentle': {'dynamics': .75, 'vibrato_cents': 18., 'vibrato_hz': 4.8, 'vibrato_delay_ms': 250.},
    'sustained': {'dynamics': .9, 'vibrato_cents': 35., 'vibrato_hz': 5.5, 'vibrato_delay_ms': 180.},
    'straight': {'vibrato_cents': 0.},
}


class CurvePoint(BaseModel):
    model_config=ConfigDict(extra='forbid')
    time_ms:float=Field(ge=0,le=600000,allow_inf_nan=False)
    value:float=Field(allow_inf_nan=False)


CURVE_LIMITS={'pitch_cents':(-1200,1200),'dynamics':(0,1),'energy':(-96,0),
              'breathiness':(-96,0),'voicing':(-96,0),'tension':(-20,20),'gender':(-1,1),'speed':(.5,2)}


class Expression(BaseModel):
    model_config = ConfigDict(extra='forbid')
    preset: Literal['neutral', 'gentle', 'sustained', 'straight'] = 'neutral'
    dynamics: float = Field(default=1., ge=0, le=1, allow_inf_nan=False)
    vibrato_cents: float = Field(default=0., ge=0, le=150, allow_inf_nan=False)
    vibrato_hz: float = Field(default=5.5, ge=1, le=12, allow_inf_nan=False)
    vibrato_delay_ms: float = Field(default=200., ge=0, le=2000, allow_inf_nan=False)
    tuning_cents: float = Field(default=0., ge=-200, le=200, allow_inf_nan=False)
    # Changes articulation within each note, never shifts project time.
    gate: float = Field(default=1., ge=.25, le=1, allow_inf_nan=False)
    attack_ms: float = Field(default=5., ge=0, le=500, allow_inf_nan=False)
    release_ms: float = Field(default=15., ge=0, le=500, allow_inf_nan=False)

    energy_db: float | None = Field(default=None, ge=-96, le=0, allow_inf_nan=False)
    breathiness_db: float | None = Field(default=None, ge=-96, le=0, allow_inf_nan=False)
    voicing_db: float | None = Field(default=None, ge=-96, le=0, allow_inf_nan=False)
    tension_db: float | None = Field(default=None, ge=-20, le=20, allow_inf_nan=False)
    gender: float | None = Field(default=None, ge=-1, le=1, allow_inf_nan=False)
    speed: float | None = Field(default=None, ge=.5, le=2, allow_inf_nan=False)
    curves:dict[Literal['pitch_cents','dynamics','energy','breathiness','voicing','tension','gender','speed'],list[CurvePoint]]=Field(default_factory=dict,max_length=8)

    @model_validator(mode='after')
    def valid_curves(self):
        if sum(len(points) for points in self.curves.values())>5000:raise ValueError('Too many vocal automation points')
        for name,points in self.curves.items():
            if not points:raise ValueError('Automation curves need at least one point')
            low,high=CURVE_LIMITS[name]
            if any(not low<=p.value<=high for p in points):raise ValueError('Vocal curve value outside '+name+' range')
            if any(a.time_ms>=b.time_ms for a,b in zip(points,points[1:])):raise ValueError('Automation times must be strictly increasing')
        return self

    @model_validator(mode='before')
    @classmethod
    def materialize_preset(cls,value):
        # Persist effective preset values so model_dump -> reload cannot turn
        # implicit preset defaults into explicit neutral overrides.
        if isinstance(value,dict):
            return {**PRESETS.get(value.get('preset','neutral'),{}),**value}
        return value

    def resolved(self):
        values = self.model_dump()
        for key, value in PRESETS[self.preset].items():
            if key not in self.model_fields_set:
                values[key] = value
        return Expression.model_validate({**values, 'preset': 'neutral'})


def f0_curve(notes, expression, timestep=.005):
    """Sample score pitch and intentional vibrato; rests have F0 zero."""
    cfg = Expression.model_validate(expression or {}).resolved()
    end = max((float(n['start_ms']) + float(n['duration_ms']) for n in notes), default=0) / 1000
    if not 0 < end <= 600:
        raise ValueError('Invalid expression timeline')
    curves=prepare_curves(cfg)
    values = [0.] * (math.ceil(end / timestep) + 1)
    for n in notes:
        start, duration = float(n['start_ms']) / 1000, float(n['duration_ms']) / 1000
        left, right = math.ceil(start / timestep - 1e-9), math.ceil((start + duration * cfg.gate) / timestep - 1e-9)
        for i in range(left, min(right, len(values))):
            elapsed = i * timestep - start
            after = max(0., elapsed - cfg.vibrato_delay_ms / 1000)
            ramp = min(1., after / .1)
            cents = cfg.tuning_cents + sample_curve(curves,'pitch_cents',i*timestep*1000,0.) + cfg.vibrato_cents * ramp * math.sin(2 * math.pi * cfg.vibrato_hz * after)
            values[i] = 440 * 2 ** ((int(n['pitch']) - 69 + cents / 100) / 12)
    return values


def apply_dynamics(audio, rate, notes, expression, gain=1.):
    """Amplitude envelope is explicit DSP; it is not a neural energy parameter."""
    import numpy as np
    cfg = Expression.model_validate(expression or {}).resolved()
    envelope = np.zeros(len(audio), dtype=np.float32)
    for n in notes:
        left = max(0, round(float(n['start_ms']) * rate / 1000))
        right = min(len(audio), round((float(n['start_ms']) + float(n['duration_ms']) * cfg.gate) * rate / 1000))
        if right <= left:
            continue
        size = right - left
        level = cfg.dynamics * int(n.get('velocity', 96)) / 127 * gain
        ramp = np.ones(size, dtype=np.float32) * level
        attack, release = min(size // 2, round(cfg.attack_ms * rate / 1000)), min(size // 2, round(cfg.release_ms * rate / 1000))
        if attack:
            ramp[:attack] *= np.linspace(0, 1, attack, endpoint=False)
        if release:
            ramp[-release:] *= np.linspace(1, 0, release)
        envelope[left:right] = np.maximum(envelope[left:right], ramp)
    if 'dynamics' in cfg.curves:
        points=cfg.curves['dynamics'];times=[p.time_ms for p in points];levels=[p.value for p in points]
        for offset in range(0,len(envelope),4096):
            end=min(len(envelope),offset+4096)
            envelope[offset:end]*=np.interp(np.arange(offset,end)*1000/rate,times,levels)
    return np.asarray(audio, dtype=np.float32) * envelope



def prepare_curves(expression):
    return {name:([p.time_ms for p in points],[p.value for p in points]) for name,points in expression.curves.items()}


def sample_curve(curves,name,time_ms,default):
    if name not in curves:return default
    times,values=curves[name];index=bisect.bisect_right(times,time_ms)-1
    if index<0:return values[0]
    if index>=len(times)-1:return values[-1]
    fraction=(time_ms-times[index])/(times[index+1]-times[index])
    return values[index]+fraction*(values[index+1]-values[index])


def ds_curves(expression,count,timestep):
    cfg=Expression.model_validate(expression or {}).resolved();curves=prepare_curves(cfg);result={}
    for name in ('energy','breathiness','voicing','tension'):
        value=getattr(cfg,name+'_db')
        if name in curves or value is not None:
            result[name]=' '.join(f'{sample_curve(curves,name,i*timestep*1000,value):.5f}' for i in range(count))
            result[name+'_timestep']=timestep
    for source,destination in (('gender','gender'),('speed','velocity')):
        value=getattr(cfg,source)
        if source in curves:
            result[destination]=' '.join(f'{sample_curve(curves,source,i*timestep*1000,value):.5f}' for i in range(count))
            result[destination+'_timestep']=timestep
        elif value is not None:
            result[destination]=(value if source=='gender' else ' '.join([str(value)]*count))
            if source=='speed':result[destination+'_timestep']=timestep
    return result
