import sys,json
from pathlib import Path
sys.path.insert(0,str(Path('mta_work').resolve()))
from app.music_interchange import MusicResult,MusicPart
from app.models import MidiNote
root=Path('mt3_memory_research');notes=json.loads((root/'actual-memory-mta-notes.json').read_text());groups={}
for n in notes:groups.setdefault((n['is_drum'],n['program']),[]).append(n)
parts=[]
for i,((drums,program),items) in enumerate(sorted(groups.items())):
 parts.append(MusicPart(id=f'memory-{i}',name='MR-MT3 memory '+('Drums' if drums else str(program)),program=None if drums else program,percussion=drums,instrument='drums' if drums else 'gm-'+str(program),source_model='mr-mt3-memory-d477dfb1',notes=[MidiNote(id=f'n-{i}-{j}',pitch=n['pitch'],start_ms=n['start_time']*1000,duration_ms=(n['end_time']-n['start_time'])*1000,velocity=n['velocity'],channel=9 if drums else i,origin='predicted',source_model='mr-mt3-memory-d477dfb1') for j,n in enumerate(items)]))
result=MusicResult(parts=parts,warnings=['Isolated actual memory-model CPU research inference; not a production-installed model or a quality certificate.','One velocity bin; velocity 127 is generated from nonzero velocity events, not estimated playing dynamics.'])
(root/'actual-memory-music.json').write_text(result.model_dump_json(indent=2)+'\n')
