"""Prove live are opt-in and must fail closed when no worker is installed."""
import json
from pathlib import Path
import wave

from app import ace_step_live_smoke as smoke
from app import ace_step_http_worker as adapter


def test_no_worker_never_reports_inference(monkeypatch):
    monkeypatch.setattr(smoke, 'configured_worker', lambda: None)
    value = smoke.test_live_inference(seconds=1)
    assert value['verified'] is False and value['attempted'] is False


def test_smoke_invalid_duration():
    import pytest
    with pytest.raises(ValueError):
        smoke.test_live_inference(seconds=0)


def test_adapter_smoke_can_reach_the_generation_entrypoint(monkeypatch, tmp_path):
    source = tmp_path / 'short.wav'
    with wave.open(str(source), 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(44100)
        wav.writeframes(b'\0\0' * 44100)
    result = tmp_path / 'output.wav'
    seen = {}

    def fake_run(plan_path, output):
        plan = json.loads(Path(plan_path).read_text())
        staged = Path(plan_path).parent / plan['source_audio'][0]['filename']
        assert staged.is_file()
        seen['ok'] = True
        output.write_bytes(source.read_bytes())

    monkeypatch.setattr(adapter, 'run', fake_run)
    monkeypatch.setattr('sys.argv', ['adapter', '--smoke-input', str(source), '--output', str(result)])
    assert adapter.main() == 0
    assert seen['ok'] and result.exists()
