"""Cross-worker adapter execution contract and safe concurrent benchmarking."""
from pathlib import Path
import subprocess
import sys

import pytest

from app import ai_unified_adapter as adapter


def test_rejects_unstaged_audio(tmp_path):
    external = tmp_path / 'external.wav'
    external.write_bytes(b'x')
    with pytest.raises(ValueError, match='staged'):
        adapter.infer({'kind':'whisper', 'source_audio':str(external)}, tmp_path/'preview.wav')


def test_rejects_unlisted_worker(tmp_path):
    (tmp_path/'source.wav').write_bytes(b'dummy')
    with pytest.raises(ValueError, match='Unsupported'):
        adapter.infer({'kind':'arbitrary', 'source_audio':str(tmp_path/'source.wav')}, tmp_path/'preview.wav')


def test_unified_worker_registry_opt_in(monkeypatch):
    from app.ai_worker_registry import resolve_worker
    monkeypatch.setenv('MTA_AI_UNIFIED_WORKERS_ENABLED','true')
    monkeypatch.setenv('MTA_AI_WORKER_ENABLED','true')
    assert resolve_worker('whisper') == Path(adapter.__file__).resolve()
    monkeypatch.delenv('MTA_AI_UNIFIED_WORKERS_ENABLED')
    assert resolve_worker('whisper') is None


def test_runner_script_imports_in_isolated_folder(tmp_path):
    proc = subprocess.run([sys.executable,str(Path(adapter.__file__).resolve()),'--help'],cwd=tmp_path,capture_output=True,text=True)
    assert proc.returncode == 0


def test_concurrent_wizard_help():
    root = Path(__file__).parents[1]
    proc=subprocess.run(['bash',str(root/'scripts/install_ace_step.sh'),'--benchmark-concurrent'],capture_output=True,text=True)
    assert proc.returncode == 2
    assert 'Missing --benchmark-remote-url' in proc.stderr


def test_chromagram_runs_without_project_bpm_in_isolated_worker(tmp_path, monkeypatch):
    import json
    import math
    import struct
    import wave

    from app.ai_execution_policy import admitted_env
    from app.model_license_policy import evaluate

    monkeypatch.setenv('MTA_DATA_DIR', str(tmp_path))
    source = tmp_path / 'source.wav'
    with wave.open(str(source), 'wb') as pcm:
        pcm.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        pcm.writeframes(b''.join(
            struct.pack('<h', round(sum(2700 * math.sin(2 * math.pi * hz * i / 16000)
                                         for hz in (130.81, 164.81, 196.00))))
            for i in range(24000)
        ))
    plan = {'kind': 'chords-ml', 'engine': 'mta-chromagram', 'source_audio': str(source),
            'options': {'preset': 'raw'}, 'bpm': None}
    request = tmp_path / 'request.json'
    request.write_text(json.dumps(plan))
    monkeypatch.setenv('MTA_AI_ADMITTED_POLICY', admitted_env('chords-ml', evaluate('chords-ml', plan))['MTA_AI_ADMITTED_POLICY'])
    result = subprocess.run(
        [sys.executable, '-I', str(Path(adapter.__file__).resolve()), '--request', str(request),
         '--output', str(tmp_path / 'preview.wav')], cwd=tmp_path,
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads((tmp_path / 'chords.json').read_text())['chords']
