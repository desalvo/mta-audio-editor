"""Mega 53 requests use the selected worker, with real WAV fixture artifacts."""
from pathlib import Path
import re

import pytest
from fastapi.testclient import TestClient

from app import ai_arranger_runtime as queue, main, mega53_runtime, native_ai_routing, storage
from app.models import Clip, Track
from test_r210_media_stems_cleanup import project as project, wav  # noqa: F401
from test_r210_standard_stem_default import STANDARD


@pytest.mark.parametrize('selection,expected', [
    ('all', {'Source', 'Vocals', 'Bass', 'Guitar', 'Piano', 'Other', 'Drums (no percussions)', 'Percussions'}),
    ('percussions', {'Source', 'Percussions'}),
    ('drums_without_percussions', {'Source', 'Drums (no percussions)'}),
    ('kick', {'Source', 'Kick'}),
    ('percussions,kick', {'Source', 'Percussions', 'Kick'}),
])
def test_remote_mega53_is_dispatched_once_per_required_source(project, monkeypatch, tmp_path, selection, expected):
    source = wav(storage.audio_path(project.id, 'source.wav'))
    project.tracks = [Track(id='t', name='Source', filename=source.name, duration_ms=100,
                            clips=[Clip(id='x', source_end_ms=100)])]
    storage.save_project(project)
    monkeypatch.setattr(main, 'NATIVE_SINGLE_USER', True)
    monkeypatch.setenv('MTA_NATIVE_SINGLE_USER', 'true')
    monkeypatch.setattr(native_ai_routing, 'is_remote', lambda kind: True)
    monkeypatch.setattr(main.STEM_SPLITTER, 'available', lambda: False)
    monkeypatch.setattr(mega53_runtime, 'infer_drums', lambda *a, **kw: pytest.fail('Local Mega 53 must not run'))
    data = wav(tmp_path / 'fixture.wav').read_bytes()
    calls = []
    def remote(kind, audio, options):
        calls.append((kind, Path(audio).name, dict(options)))
        if kind == 'demucs':
            return {'audio': {f'stem_{name}.wav': data for name in STANDARD}}, 'demucs-job'
        assert kind == 'drumsep' and options['model'] == 'mvsep-mega53'
        targets = set(options['targets'])
        filenames = {'drums': 'drums_without_percussions.wav', 'percussion': 'percussions.wav', 'kick': 'kick.wav'}
        return {'audio': {filenames[name]: data for name in targets}}, 'mega-job'
    monkeypatch.setattr(main, '_native_remote_infer', remote)
    pending = []
    monkeypatch.setattr(queue, '_spawn', lambda jid, fn, **kw: pending.append(fn))
    client = TestClient(main.app, headers={'x-mta-request': '1'})
    response = client.post(f'/api/projects/{project.id}/tracks/t/stem-jobs', params={
        'stem_targets': selection, 'split_percussions': 'true', 'percussion_method': 'mvsep-mega53',
    })
    assert response.status_code == 200, response.text
    jid = response.json()['id']
    pending[0](tmp_path / 'progress.json')
    assert main.STEM_JOBS[jid]['status'] == 'completed', main.STEM_JOBS[jid].get('error')
    assert {track.name for track in storage.load_project(project.id).tracks} == expected
    mega_calls = [x for x in calls if x[0] == 'drumsep']
    groups = [x for x in mega_calls if set(x[2]['targets']) == {'drums', 'percussion'}]
    assert len(groups) == (0 if selection == 'kick' else 1)
    if groups:
        assert groups[0][1] == 'source.wav'
    parts = [x for x in mega_calls if set(x[2]['targets']) == {'kick'}]
    assert len(parts) == int('kick' in selection)
    if parts:
        assert parts[0][1] == 'drums.wav'


def test_remote_mega53_rejects_wrong_or_corrupt_artifacts_without_local_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(mega53_runtime, 'infer_drums', lambda *a, **kw: pytest.fail('No local fallback'))
    payload = wav(tmp_path / 'valid.wav').read_bytes()
    for audio in ({'percussions.wav': payload},
                  {'drums_without_percussions.wav': payload, 'percussions.wav': b'bad'},
                  {'drums_without_percussions.wav': payload, 'percussions.wav': payload, 'extra.wav': payload}):
        with pytest.raises(ValueError):
            mega53_runtime.dispatch_drums(tmp_path / 'input.wav', tmp_path / 'out', {'drums', 'percussion'},
                remote=lambda *a: ({'audio': audio}, 'job'))
    assert not (tmp_path / 'out').exists()


def test_missing_mega53_setting_names_the_executing_worker(tmp_path, monkeypatch):
    monkeypatch.setattr('app.model_license_policy.evaluate_model', lambda _: None)
    monkeypatch.delenv('MTA_MEGA53_ROOT', raising=False)
    with pytest.raises(RuntimeError, match='worker.*MTA_MEGA53_ROOT'):
        mega53_runtime.infer(tmp_path / 'source.wav', tmp_path / 'out')


def test_join_toolbar_is_icon_only_and_has_tooltip_and_accessible_name():
    js = (Path(__file__).resolve().parents[1] / 'app/static/app.js').read_text()
    button = re.search(r'<button id="toolJoin".*?</button>', js).group(0)
    assert 'title="${tr(' in button and 'aria-label="${tr(' in button
    assert '<strong aria-hidden="true">⋈</strong></button>' in button
    assert "${tr('Join','Unisci')}" not in button


def test_unified_worker_maps_hi_hat_to_upstream_hh(tmp_path, monkeypatch):
    from app import ai_unified_adapter as worker
    monkeypatch.setattr('app.model_license_policy.evaluate', lambda *a, **kw: None)
    source = wav(tmp_path / 'source.wav')
    observed = []
    def fake_infer(audio, output, targets, **kwargs):
        observed.append((audio, targets))
        return [wav(output / 'hh.wav')]
    monkeypatch.setattr(mega53_runtime, 'infer_drums', fake_infer)
    monkeypatch.setattr(worker, '_artifacts', lambda folder, entries: observed.append(entries))
    worker.infer({'kind': 'drumsep', 'model': 'mvsep-mega53', 'targets': ['hi-hat'],
                  'source_audio': str(source)}, tmp_path / 'output.wav')
    assert observed[0] == (source, {'hh'})
    assert observed[1][0][0].name == 'hh.wav'


@pytest.mark.parametrize('stderr,category', [
    ('RuntimeError: Mega 53 runtime upstream non configurato nel processo che esegue il worker: PRIVATE', 'mega53_configuration_missing'),
    ('RuntimeError: Mega 53 requires a local absolute upstream directory', 'mega53_configuration_missing'),
    ('RuntimeError: Mega 53 requires a regular absolute config file', 'mega53_configuration_missing'),
    ('RuntimeError: Mega 53 checkpoint SHA-256 mismatch', 'mega53_checkpoint_mismatch'),
])
def test_cgroup_diagnostic_is_useful_and_does_not_expose_worker_details(stderr, category):
    import json
    from app.ai_cgroup_metering import _worker_failure, _FAILURE_HINTS, safe_failure_metadata
    value = _worker_failure(stderr, 1)
    assert value['category'] == category
    assert 'PRIVATE' not in json.dumps(safe_failure_metadata(value))
    assert 'Mega 53' in _FAILURE_HINTS[category] or 'MTA_MEGA53_ROOT' in _FAILURE_HINTS[category]


def test_local_mega53_missing_configuration_fails_before_demucs(project, monkeypatch, tmp_path, local_native_ai):
    source = wav(storage.audio_path(project.id, 'source.wav'))
    project.tracks = [Track(id='t', name='Source', filename=source.name, duration_ms=100,
                            clips=[Clip(id='x', source_end_ms=100)])]
    storage.save_project(project)
    monkeypatch.delenv('MTA_MEGA53_ROOT', raising=False)
    monkeypatch.setattr(main.STEM_SPLITTER, 'available', lambda: True)
    monkeypatch.setattr(main.STEM_SPLITTER, 'split', lambda *a, **kw: pytest.fail('Demucs should not run'))
    pending = []
    monkeypatch.setattr(queue, '_spawn', lambda jid, fn, **kw: pending.append(fn))
    client = TestClient(main.app, headers={'x-mta-request': '1'})
    response = client.post(f'/api/projects/{project.id}/tracks/t/stem-jobs', params={
        'stem_targets': 'percussions', 'percussion_method': 'mvsep-mega53',
    })
    assert response.status_code == 200, response.text
    jid = response.json()['id']
    with pytest.raises(RuntimeError, match='MTA_MEGA53_ROOT'):
        pending[0](tmp_path / 'progress.json')
    job = main.STEM_JOBS[jid]
    assert job['status'] == 'failed' and 'MTA_MEGA53_ROOT' in job['error']


def test_benchmark_fingerprint_includes_mega53_dispatch_and_worker_code(monkeypatch):
    from app import percussion_benchmark as bench
    paths = []
    def observed(path):
        paths.append(path.name)
        return path.name
    monkeypatch.setattr(bench, 'digest', observed)
    assert bench.pipeline_hash()
    assert {'mega53_runtime.py', 'ai_unified_adapter.py'} <= set(paths)


def test_server_local_unified_worker_preflight_uses_its_inherited_environment(project, monkeypatch, tmp_path):
    import threading
    from app import ai_pull_coordinator, ai_worker_registry
    source = wav(storage.audio_path(project.id, 'source.wav'))
    jid = 'local-preflight-test'
    monkeypatch.setattr(main, 'NATIVE_SINGLE_USER', False)
    monkeypatch.setattr(ai_pull_coordinator, 'mode', lambda: 'local')
    monkeypatch.setattr(ai_worker_registry, 'resolve_worker', lambda kind: Path(main.__file__).with_name('ai_unified_adapter.py').resolve())
    monkeypatch.delenv('MTA_MEGA53_ROOT', raising=False)
    monkeypatch.setattr(main.STEM_SPLITTER, 'split', lambda *a, **kw: pytest.fail('Demucs should not run'))
    main.STEM_JOBS[jid] = {'id': jid, 'project_id': project.id, 'model': 'htdemucs',
                           'cancel_event': threading.Event(), 'status': 'queued',
                           'split_percussions': True, 'stem_targets': ['percussions'],
                           'percussion_method': 'mvsep-mega53'}
    main._stem_split_worker(jid, source, True)
    assert main.STEM_JOBS[jid]['status'] == 'failed'
    assert 'MTA_MEGA53_ROOT' in main.STEM_JOBS[jid]['error']
    assert source.is_file()
