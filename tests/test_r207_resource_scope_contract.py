from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_metering_not_based_on_host_counters():
    source = (ROOT / 'app/ai_metering_agent.py').read_text()
    assert 'os.wait4' in source
    assert '/proc/stat' not in source
    assert '/proc/diskstats' not in source
    assert 'nvidia-smi' not in source
    assert 'rocm-smi' not in source


def test_physical_io_uses_resolved_process_directory(tmp_path,monkeypatch):
    from app import ai_metering_agent,linux_proc_view
    (tmp_path/'io').write_text('read_bytes: 17\nwrite_bytes: 29\nrchar: 999999\n')
    observed=[]
    monkeypatch.setattr(linux_proc_view,'directory',lambda pid:observed.append(pid) or tmp_path)
    assert ai_metering_agent._io(123)==(17,29)
    assert observed==[123]
    monkeypatch.setattr(linux_proc_view,'directory',lambda pid:None)
    assert ai_metering_agent._io(123) is None

def test_partial_process_tree_not_marked_complete():
    source = (ROOT / 'app/ai_metering_agent.py').read_text()
    assert 'result.isolated else None' in source
    assert "source=result.source if result.isolated else 'unmetered'" in source
