"""Piecewise source-domain tempo, continuous PPQ and explicit bar rephasing."""
import bisect
import math


class TempoMap:
    def __init__(self,data):
        ratio=max(.25,min(4,float(data.get('bpm',120))/float(data.get('base_bpm') or data.get('bpm',120))))
        bpm=float(data.get('metronome_bpm') or data.get('bpm',120))/ratio
        signature=data.get('metronome_time_signature') or data.get('time_signature','4/4')
        origin=float(data.get('metronome_grid_origin_ms',0))+float(data.get('metronome_shift_ms',0))
        mode=data.get('metronome_mode','fixed');points=[(0.,bpm,signature,False)]
        if mode=='zones':
            marks=sorted((m for m in data.get('markers',[]) if not m.get('disabled') and not m.get('deleted') and m['time_ms']>0),key=lambda m:m['time_ms'])
            boundaries=[(0,'START')]+[(m['time_ms'],m['id']) for m in marks]+[(86400000,'END')]
            points=[]
            for (start,left),(_,right) in zip(boundaries,boundaries[1:]):
                key=f'{left}|{right}'
                def manual(name,fallback):
                    values=data.get(name,{})
                    if key in values:return values[key]
                    matching=[v for k,v in values.items() if k.split('|')[0]==left or k.split('|')[-1]==right]
                    return matching[0] if len(matching)==1 else fallback
                tempo=manual('metronome_manual_zone_bpms',data.get('metronome_zone_bpms',{}).get(str(start),bpm*ratio))
                meter=manual('metronome_manual_zone_signatures',data.get('metronome_zone_signatures',{}).get(str(start),signature))
                points.append((float(start),float(tempo)/ratio,meter,True))
            origin=0
        elif mode=='adaptive' and data.get('adaptive_tempo_map'):
            raw=sorted(data['adaptive_tempo_map'],key=lambda p:p['time_ms']);points=[]
            for i,item in enumerate(raw):
                tempo=float(item['bpm'])/ratio
                if i+1<len(raw):
                    dt=raw[i+1]['time_ms']-item['time_ms'];beats=raw[i+1]['beat_index']-item['beat_index']
                    if dt>0 and beats>0:tempo=60000*beats/dt/ratio
                points.append((float(item['time_ms']),tempo,data.get('time_signature','4/4'),False))
            origin=points[0][0]
        self.times=[];self.pieces=[];previous=None;ppq=0.;bar=0.
        for at,tempo,meter,rephase in points:
            if not math.isfinite(tempo) or not 0<tempo<=2000:raise ValueError('Invalid host tempo map')
            n,d=map(int,meter.split('/'))
            if previous is None:ppq=(at-origin)*tempo/60000;bar=math.floor(ppq/(n*4/d))*(n*4/d)
            else:ppq+=(at-previous[0])*previous[1]/60000
            if rephase or (previous and meter!=previous[2]):bar=ppq
            if self.times and at==self.times[-1]:self.times.pop();self.pieces.pop()
            self.times.append(at);self.pieces.append((tempo,n,d,ppq,bar));previous=(at,tempo,meter)

    def position(self,ms):
        i=max(0,bisect.bisect_right(self.times,ms)-1);bpm,n,d,ppq,origin=self.pieces[i]
        ppq+=(ms-self.times[i])*bpm/60000;bar=n*4/d
        return bpm,n,d,ppq,origin+math.floor((ppq-origin)/bar+1e-10)*bar

    def boundaries(self,start,count,rate):
        end=start+count
        return sorted({start,end,*[round(t*rate/1000) for t in self.times if start<round(t*rate/1000)<end]})
