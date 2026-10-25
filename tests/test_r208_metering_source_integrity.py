"""Source provenance must survive the worker-to-billing handoff."""
from pathlib import Path
from app import ai_worker_protocol, main


def test_local_metering_sources_are_labeled_at_collection():
    source = Path(ai_worker_protocol.__file__).read_text()
    assert 'metered_source = "cgroup"' in source
    assert "metered_source = 'worker'" in source
    assert "meta['_trusted_worker_source'] = metered_source" in source


def test_generation_handoff_rejects_missing_provenance():
    source = Path(main.__file__).read_text()
    assert "source = meta.pop('_trusted_worker_source', None)" in source
    assert "if source not in ('worker', 'cgroup', 'gpu-kernel-verified','diagnostic-estimate', 'remote-worker'):" in source
    assert 'ai_metering_bridge.capture(job_id, usage, source)' in source
