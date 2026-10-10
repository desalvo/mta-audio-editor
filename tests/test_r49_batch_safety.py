"""Regression checks for the r45-r49 batch delivery."""
import json
import os
import wave
from pathlib import Path

import pytest

from native.vst3_probe.batch_wav_cli import _write_report, main, run_batch


def _case(tmp_path, *, frames=32):
    source = tmp_path / 'in.wav'
    with wave.open(str(source), 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(48000)
        wav.writeframes(b'\0\0' * frames)
    manifest = tmp_path / 'batch.json'
    manifest.write_text(json.dumps({'schema': 1, 'jobs': [
        {'source': 'in.wav', 'destination': 'out.wav', 'plugins': [['plugin', 'a' * 32]]}
    ]}), encoding='utf-8')
    return source, manifest


def test_dry_run_reports_total_frames(tmp_path):
    _, manifest = _case(tmp_path)
    result = run_batch(manifest, '/not/used', dry_run=True)
    assert result['total_frames'] == 32
    assert result['processed'] == 0


def test_frame_budget_rejected_before_render(tmp_path):
    _, manifest = _case(tmp_path)
    with pytest.raises(ValueError, match='frame budget'):
        run_batch(manifest, '/not/used', dry_run=True, max_total_frames=31)


def test_invalid_budget_rejected(tmp_path):
    _, manifest = _case(tmp_path)
    for budget in (True, 0, -1, 999999999):
        with pytest.raises(ValueError, match='frame budget'):
            run_batch(manifest, '/not/used', dry_run=True, max_total_frames=budget)


def test_hard_link_alias_rejected(tmp_path):
    source, manifest = _case(tmp_path)
    os.link(source, tmp_path / 'out.wav')
    with pytest.raises(ValueError, match='hard link'):
        run_batch(manifest, '/not/used', dry_run=True)


def test_json_report_written_atomically(tmp_path):
    target = tmp_path / 'report.json'
    target.write_text('old', encoding='utf-8')
    _write_report(target, {'status': 'ready', 'processed': 0})
    assert json.loads(target.read_text())['processed'] == 0
    assert not list(tmp_path.glob('.mta-report-*'))


def test_cli_preflight_with_report(tmp_path):
    _, manifest = _case(tmp_path)
    report = tmp_path / 'receipt.json'
    assert main([str(manifest), '--probe', '/unused', '--dry-run', '--report', str(report)]) == 0
    assert json.loads(report.read_text())['total_frames'] == 32
    assert not (tmp_path / 'out.wav').exists()


def test_r41_no_unused_batch_import():
    source = (Path(__file__).parent / 'test_r41_vst3_sample_rates.py').read_text()
    assert 'from native.vst3_probe.batch_wav_cli import run_batch' not in source
