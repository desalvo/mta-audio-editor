from pathlib import Path
from types import SimpleNamespace
import subprocess
import pytest

from app.audio_engine import render_track
from app.models import Track, Clip, InsertPlugin
import app.audio_engine as engine
import app.vst3_host as host


def track(paths):
    return Track(id='track', name='Test', filename='src.wav', channels=2,
                 clips=[Clip(id='clip', source_end_ms=100)],
                 inserts=[InsertPlugin(id=f'v{i}', plugin='vst3', params={'path': path})
                          for i, path in enumerate(paths)])


def setup(monkeypatch):
    def ffmpeg(cmd):
        Path(cmd[-1]).write_bytes(b'WAV input')
        return ''
    monkeypatch.setattr(engine, '_run', ffmpeg)
    monkeypatch.setattr(host, 'validate_plugin_path', lambda name: Path(name))


def test_atomic_chain_publishes_last_successful_output(tmp_path, monkeypatch):
    setup(monkeypatch)
    result = tmp_path / 'done.wav'
    result.write_bytes(b'original')
    calls = []
    def run(cmd, **kwargs):
        calls.append(cmd)
        Path(cmd[5]).write_bytes(b'plugin ' + str(len(calls)).encode())
        return SimpleNamespace(returncode=0, stderr='')
    monkeypatch.setattr(engine.subprocess, 'run', run)
    render_track(track(['/a.vst3', '/b.vst3']), tmp_path/'input.wav', result)
    assert result.read_bytes() == b'plugin 2'
    assert len(calls) == 2
    assert not list(tmp_path.glob('.done.wav.*'))


def test_failed_second_plugin_preserves_previous_export(tmp_path, monkeypatch):
    setup(monkeypatch)
    result = tmp_path / 'done.wav'
    result.write_bytes(b'old good output')
    calls = []
    def run(cmd, **kwargs):
        calls.append(cmd)
        Path(cmd[5]).write_bytes(b'partial broken output')
        return SimpleNamespace(returncode=1 if len(calls)==2 else 0, stderr='failure')
    monkeypatch.setattr(engine.subprocess, 'run', run)
    with pytest.raises(RuntimeError, match='VST3 failed'):
        render_track(track(['/a.vst3', '/b.vst3']), tmp_path/'input.wav', result)
    assert result.read_bytes() == b'old good output'


def test_preflight_validates_all_before_render(tmp_path, monkeypatch):
    setup(monkeypatch)
    result = tmp_path / 'done.wav'
    result.write_bytes(b'old')
    def validate(name):
        if name == '/missing.vst3':
            raise FileNotFoundError('missing plugin')
        return Path(name)
    monkeypatch.setattr(host, 'validate_plugin_path', validate)
    monkeypatch.setattr(engine, '_run', lambda cmd: pytest.fail('render happened before preflight'))
    with pytest.raises(FileNotFoundError):
        render_track(track(['/good.vst3', '/missing.vst3']), tmp_path/'input.wav', result)
    assert result.read_bytes() == b'old'


def test_empty_and_timeout_fail_without_publish(tmp_path, monkeypatch):
    setup(monkeypatch)
    result = tmp_path / 'done.wav'
    result.write_bytes(b'old')
    monkeypatch.setattr(engine.subprocess, 'run', lambda cmd, **kwargs: SimpleNamespace(returncode=0, stderr=''))
    with pytest.raises(RuntimeError, match='produced no audio'):
        render_track(track(['/good.vst3']), tmp_path/'input.wav', result)
    assert result.read_bytes() == b'old'
    def timeout(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 600)
    monkeypatch.setattr(engine.subprocess, 'run', timeout)
    with pytest.raises(RuntimeError, match='timed out'):
        render_track(track(['/good.vst3']), tmp_path/'input.wav', result)
    assert result.read_bytes() == b'old'
