from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_metering_not_based_on_host_counters():
    source = (ROOT / 'app/ai_metering_agent.py').read_text()
    assert 'os.wait4' in source
    assert "f'/proc/{pid}/io'" in source
    assert '/proc/stat' not in source
    assert '/proc/diskstats' not in source
    assert 'nvidia-smi' not in source
    assert 'rocm-smi' not in source

def test_partial_process_tree_not_marked_complete():
    source = (ROOT / 'app/ai_metering_agent.py').read_text()
    assert 'result.isolated else None' in source
    assert "source=result.source if result.isolated else 'unmetered'" in source
