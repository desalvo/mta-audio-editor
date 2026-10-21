"""Post-hoc offset sensitivity study; never adjusts model predictions for certification."""
import json, collections, argparse
from bisect import bisect_left,bisect_right
from pathlib import Path
import mido, numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import maximum_bipartite_matching

def notes_reference(path):
    mid=mido.MidiFile(path,clip=True); tempo=500000; t=0.;prog=[0]*16
    active=collections.defaultdict(collections.deque); out=[]
    for event in mido.merge_tracks(mid.tracks):
        t+=mido.tick2second(event.time,mid.ticks_per_beat,tempo)
        if event.type=='set_tempo':tempo=event.tempo
        elif event.type=='program_change':prog[event.channel]=event.program
        elif event.type=='note_on' and event.velocity>0:
            active[event.channel,event.note].append((t,prog[event.channel]))
        elif event.type=='note_off' or (event.type=='note_on' and event.velocity==0):
            a=active[event.channel,event.note]
            if a:
                st,pr=a.popleft();out.append(('drums' if event.channel==9 else pr,event.note,st,t))
    return out

def match(reference,prediction,shift=0.,program_agnostic=False,onset=.05,offset=.1):
    grouped=collections.defaultdict(list)
    for j,(program,pitch,start,end) in enumerate(reference):
        grouped[pitch if program_agnostic else (program,pitch)].append((start,end,j))
    for k in grouped:grouped[k].sort()
    times={k:[x[0] for x in v] for k,v in grouped.items()}
    rows=[];cols=[]
    for i,(program,pitch,start,end) in enumerate(prediction):
        k=pitch if program_agnostic else (program,pitch)
        events=grouped.get(k,[]); loc=times.get(k,[])
        for ref_start,ref_end,j in events[bisect_left(loc,start+shift-onset):bisect_right(loc,start+shift+onset)]:
            if abs(ref_end-(end+shift))<=offset:
                rows.append(i);cols.append(j)
    if not rows:return 0
    matrix=csr_matrix((np.ones(len(rows),dtype=np.int8),(rows,cols)),shape=(len(prediction),len(reference)))
    return int((maximum_bipartite_matching(matrix,perm_type='column')>=0).sum())

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--midi',required=True);parser.add_argument('--prediction',required=True);parser.add_argument('--output',required=True)
    a=parser.parse_args();reference=notes_reference(a.midi);data=json.loads(Path(a.prediction).read_text());prediction=[('drums' if n['is_drum'] else n['program'],n['pitch'],n['start_time'],n['end_time']) for n in data['notes']]
    shifts=[round(i*.05,3) for i in range(-20,21)]
    values=[{'shift_seconds':s,'strict_matches':match(reference,prediction,s),'program_agnostic_matches':match(reference,prediction,s,True)} for s in shifts]
    # Only the ORIGINAL zero-offset comparison can be used as the fixed baseline.
    zero=next(v for v in values if v['shift_seconds']==0)
    top_strict=max(values,key=lambda v:v['strict_matches']);top_any=max(values,key=lambda v:v['program_agnostic_matches'])
    report={'source':'MR-MT3 real ROCm full-track inference','kind':'posthoc_alignment_sensitivity_not_certification','reference_notes':len(reference),'prediction_notes':len(prediction),'fixed_zero_offset':zero,'best_strict_exploratory':top_strict,'best_program_agnostic_exploratory':top_any,'sweep':values,'note':'No offsets were fitted or applied to outputs. Best scores are optimistic in-sample diagnostics; use independently measured offset for certification.'}
    Path(a.output).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='sweep'},indent=2))
if __name__=='__main__':main()
