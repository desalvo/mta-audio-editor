import importlib.util, pathlib, subprocess
from unittest.mock import patch
p=pathlib.Path(__file__).resolve().parents[1]/'app'/'ace_gpu_process_meter.py'
spec=importlib.util.spec_from_file_location('ace_meter',p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def test_gfx_parser():
    assert m.gfx_ns_for_pid({'gpu0':{'PROCESS_INFO':[{'PID':123,'USAGE':{'GFX':1_234_000_000}},{'PID':124,'USAGE':{'GFX':999}}]}},123)==1_234_000_000
    assert m.gfx_ns_for_pid({'gpu0':{'PROCESS_INFO':[{'PID':124,'USAGE':{'GFX':999}}]}},123) is None
    assert m.gfx_ns_for_pid({'PID':123,'USAGE':{'GFX':'120 ns'}},123)==120
    assert m.gfx_ns_for_pid({'PID':123,'USAGE':{'GFX':'12%'}},123) is None
    assert m.gfx_ns_for_pid({'PID':123,'USAGE':{'GFX':float('nan')}},123) is None

def test_meter_samples_process_delta_not_wall_clock():
    responses=[{'PID':55,'USAGE':{'GFX':1_000_000_000}}, {'PID':55,'USAGE':{'GFX':3_500_000_000}}]
    class Result:
        def __init__(self,index): self.stdout=__import__('json').dumps(responses[index])
    i=iter([0,1])
    with patch.object(m,'_ace_pid',return_value=55),patch.object(m,'_cpu_seconds',side_effect=[30,31.5]),patch.object(m.subprocess,'run',side_effect=lambda *a,**k:Result(next(i))):
        meter=m.AceProcessMeter('http://127.0.0.1:8001')
        assert meter.sample()=={}
        assert meter.sample()=={'gpu_seconds_estimated':2.5,'cpu_seconds_estimated':1.5}

def test_remote_not_measured():
    with patch.object(m,'_ace_pid',side_effect=AssertionError('no local PID lookup for remote')):
        assert m.AceProcessMeter('https://other.example:443').sample()=={}

def test_missing_amd_smi_does_not_fabricate_gpu():
    with patch.object(m,'_ace_pid',return_value=55),patch.object(m,'_cpu_seconds',return_value=None),patch.object(m.subprocess,'run',side_effect=FileNotFoundError):
        assert m.AceProcessMeter('http://localhost:8001').sample()=={}
