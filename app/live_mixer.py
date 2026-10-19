"""Validated, ephemeral mixer changes; no file paths or plugin code from clients."""
import math
from .models import Project


def apply(project, patch):
    if not isinstance(patch,dict) or set(patch)!={'tracks','master_volume_db'}:
        raise ValueError('Invalid live mixer controls')
    tracks=patch['tracks']
    if not isinstance(tracks,list) or len(tracks)!=len(project.tracks):raise ValueError('Invalid live mixer tracks')
    data=project.model_dump(mode='json');known={t['id']:t for t in data['tracks']};seen=set()
    limits={'gain_db':(-24,24),'volume_db':(-120,24),'pan':(-1,1)}
    for track in tracks:
        if not isinstance(track,dict) or set(track)!={'id','gain_db','volume_db','pan','mute','solo'}:raise ValueError('Invalid live mixer track controls')
        tid=track['id']
        if not isinstance(tid,str) or tid not in known or tid in seen:raise ValueError('Invalid live mixer track identity')
        seen.add(tid)
        for key,(low,high) in limits.items():
            value=track[key]
            if type(value) not in (int,float) or not math.isfinite(value) or not low<=value<=high:raise ValueError('Invalid live mixer '+key)
        if type(track['mute']) is not bool or type(track['solo']) is not bool:raise ValueError('Invalid live mixer mute/solo')
        known[tid].update(track)
    value=patch['master_volume_db']
    if type(value) not in (int,float) or not math.isfinite(value) or not -120<=value<=24:raise ValueError('Invalid live master volume')
    data['master_volume_db']=value
    return Project.model_validate(data)
