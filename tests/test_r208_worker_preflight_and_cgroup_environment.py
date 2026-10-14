"""Local worker cancellation must stop preparation; cgroup must inherit job progress configuration."""
import json
import threading
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest
from app import ai_worker_protocol as worker


def _project():
    return SimpleNamespace(id='p', tracks=[SimpleNamespace(id='t', filename='t.wav')])


def test_pre_cancelled_worker_never_resolves_or_renders(monkeypatch, tmp_path):
    executable = tmp_path / 'worker.py'
    executable.write_text('pass')
    monkeypatch.setattr(worker, 'configured_worker', lambda: executable)
    cancelled = threading.Event()
    cancelled.set()
    with pytest.raises(worker.WorkerUnavailable, match='cancelled'):
        worker.run_worker_with_project_audio({'input_source': 'track', 'input_track_id': 't'},
                                             _project(), lambda *_: pytest.fail('resolved after cancellation'),
                                             cancel_event=cancelled)


def test_cancel_during_render_never_starts_worker(monkeypatch, tmp_path):
    executable = tmp_path / 'worker.py'
    executable.write_text('pass')
    monkeypatch.setattr(worker, 'configured_worker', lambda: executable)
    cancelled = threading.Event()
    source = tmp_path / 't.wav'
    source.write_bytes(b'a')
    from app import audio_engine
    def render(*args, **kwargs):
        cancelled.set()
        pytest.fail('render should not start after cancellation')
    # Cancel as source resolution completes, before rendering.
    monkeypatch.setattr(audio_engine, 'render_track', render)
    def resolve(*args):
        cancelled.set()
        return source
    with pytest.raises(worker.WorkerUnavailable, match='cancelled'):
        # The cancellation immediately before track rendering must stop the call.
        worker.run_worker_with_project_audio({'input_source': 'track', 'input_track_id': 't'},
                                             _project(), resolve, cancel_event=cancelled)


def test_cgroup_worker_receives_progress_environment(monkeypatch, tmp_path):
    executable = tmp_path / 'worker.py'
    executable.write_text('pass')
    monkeypatch.setattr(worker, 'configured_worker', lambda: executable)
    monkeypatch.setenv('MTA_AI_CGROUP_PARENT', '/sys/fs/cgroup/delegated')
    source = tmp_path / 't.wav'
    with wave.open(str(source), 'wb') as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(44100); f.writeframes(b'\0\0' * 441)
    from app import audio_engine, ai_cgroup_metering
    monkeypatch.setattr(audio_engine, 'render_track', lambda track, src, dst, **kw: Path(dst).write_bytes(source.read_bytes()))
    progress = tmp_path / 'progress.json'
    called = {}
    def fake_cgroup(command, **kwargs):
        called.update(kwargs)
        output = Path(command[command.index('--output') + 1])
        output.write_bytes(source.read_bytes())
        return SimpleNamespace(usage={'cpu_seconds': 0.3}, exit_code=0)
    monkeypatch.setattr(ai_cgroup_metering, 'run_cgroup_process', fake_cgroup)
    _, meta = worker.run_worker_with_project_audio({'input_source': 'track', 'input_track_id': 't'},
                                                   _project(), lambda *_: source, progress_file=progress)
    assert called['env']['MTA_AI_PROGRESS_FILE'] == str(progress)
    assert meta['_trusted_worker_source'] == 'cgroup'
