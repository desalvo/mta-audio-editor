"""Exercise real project-clock quantization, source/clip mapping and swing."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_quantize_project_grid_variable_tempo_clip_offsets_and_strength():
    code = r'''
const assert=require('assert'),m=require(process.argv[1]),{Clock}=require(process.argv[2]);
const note={id:'n',start_ms:10,duration_ms:250,pitch:60,velocity:90,channel:2},other={...note,id:'other',start_ms:15};
const track={delay_ms:100,clips:[{source_start_ms:0,source_end_ms:500,timeline_start_ms:1100}]};
const clock=new Clock({bpm:120,time_signature:'4/4',musical_origin_ms:1000});
const target=n=>m.projectGridTarget(n,track,clock,4,0),before=JSON.stringify([note,other]);
const out=m.transform([note,other],new Set(['n']),'quantize',{quantizeTarget:target});
assert.equal(out[0].start_ms,50);assert.deepEqual(out[1],other);assert.equal(JSON.stringify([note,other]),before);
assert.equal(out[0].origin,'manual');assert.equal(out[0].confidence,null);assert.equal(out[0].duration_ms,250);assert.equal(out[0].channel,2);
assert.equal(m.transform([note],new Set(['n']),'quantize',{quantizeTarget:target,strength:.5})[0].start_ms,30);
assert.equal(m.transform([note],new Set(['n']),'quantize',{quantizeTarget:target,strength:0})[0].start_ms,10);
const project={bpm:120,time_signature:'4/4',musical_origin_ms:0,metronome_mode:'zones',markers:[{id:'m',time_ms:2000}],metronome_manual_zone_bpms:{'START|m':120,'m|END':60}};
const zoned=new Clock(project),late={...note,start_ms:2110},q=n=>m.projectGridTarget(n,{},zoned,4,0);
assert(Math.abs(q(late)-2000)<1e-8);
assert.equal(m.transform([late],new Set(['n']),'quantize',{step:125})[0].start_ms,2125);
const adaptive=new Clock({bpm:120,time_signature:'4/4',musical_origin_ms:0,metronome_mode:'adaptive',adaptive_tempo_map:[{time_ms:0,beat_index:0,bpm:120},{time_ms:2000,beat_index:4,bpm:60},{time_ms:6000,beat_index:8,bpm:60}]});
assert(Math.abs(m.projectGridTarget(late,{},adaptive,4,0)-2000)<1e-8);
const partial=new Clock({...project,markers:[{id:'m',time_ms:2100}]});assert(Math.abs(m.projectGridTarget({...note,start_ms:2140},{},partial,4,0)-2100)<1e-8);
assert.equal(m.nearestGrid(66,100,.49),0);assert.equal(m.nearestGrid(100,100,.49),149);
assert.throws(()=>m.transform([note],new Set(['n']),'quantize',{quantizeTarget:()=>NaN}));
assert.equal(m.transform([{...note,start_ms:5}],new Set(['n']),'quantize',{quantizeTarget:()=>-100})[0].start_ms,0);
'''
    result = subprocess.run(['node', '-e', code, str(ROOT/'app/static/midi_editing.js'), str(ROOT/'app/static/musical_clock.js')], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
