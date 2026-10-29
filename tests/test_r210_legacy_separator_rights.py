"""Rights at legacy desktop/opaque and already-loaded separator boundaries."""
import json
import base64
import os
import subprocess
import sys
import types
from pathlib import Path
from unittest.mock import Mock

import pytest
from app import model_license_policy as policy
from test_r208_unified_adapter_billing_e2e import operator as operator, source_audio  # noqa: F401
from test_r210_execution_entry_acceptance import env as env, registered as registered, api  # noqa: F401

UVR = 'UVR_MDXNET_KARA_2.onnx'
ROFORMER = 'mel_band_roformer_karaoke_gabox_v2.ckpt'


@pytest.fixture
def local(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR', str(tmp_path))
    monkeypatch.setattr(policy, '_path', lambda: tmp_path / 'policy.json')
    monkeypatch.delenv('MTA_DEMUCS_LOCAL_REPO', raising=False)
    monkeypatch.delenv('MTA_LEAD_BACKING_COMMAND', raising=False)
    return tmp_path


def permission(folder, model, mode='cost_recovery'):
    (folder / 'policy.json').write_text(json.dumps({model: {'mode': mode}}))


@pytest.mark.parametrize('frozen', [False, True])
@pytest.mark.parametrize('denial', ['disabled', 'commercial_free_only', 'commercial_off', 'corrupt'])
def test_native_demucs_denies_before_runtime_output_or_frozen_import(local, monkeypatch, frozen, denial):
    from app import plugins
    monkeypatch.setattr(plugins.sys, 'frozen', frozen, raising=False)
    probe = Mock(side_effect=AssertionError('Denied model reached a runtime probe'))
    monkeypatch.setattr(plugins.DemucsStemSplitter, 'available', probe)
    mode = 'free_only' if denial == 'commercial_free_only' else 'cost_recovery' if denial == 'commercial_off' else 'disabled'
    permission(local, 'demucs', mode)
    if denial == 'corrupt': (local / 'policy.json').write_text('{')
    if denial == 'commercial_off': (local / 'commercial-service.json').write_text('{"enabled":false}')
    if denial == 'commercial_free_only':
        from app import auth
        from app.regime_operation_fence import initialize
        (local / 'service-regime.json').write_text('{"regime":"COMMERCIAL","revision":0}')
        with auth.db() as c:
            c.execute('BEGIN IMMEDIATE')
            initialize(c, initial_regime='COMMERCIAL')
    with pytest.raises((policy.LicenseDenied, json.JSONDecodeError)):
        plugins.DemucsStemSplitter.split(local / 'source.wav', local / 'output')
    probe.assert_not_called()
    assert not (local / 'output').exists()


@pytest.mark.parametrize('frozen', [False, True])
@pytest.mark.parametrize('model,count', [('foreign', 0), ('foreign', 2), ('/unreviewed/weights.pt', 6)])
def test_native_demucs_cannot_replace_an_unknown_request_with_a_different_checkpoint(local, monkeypatch, frozen, model, count):
    from app import plugins
    monkeypatch.setattr(plugins.sys, 'frozen', frozen, raising=False)
    probe = Mock(side_effect=AssertionError('Unknown selector reached runtime'))
    monkeypatch.setattr(plugins.DemucsStemSplitter, 'available', probe)
    with pytest.raises(ValueError, match='Demucs'):
        plugins.DemucsStemSplitter.split(local / 'input', local / 'output', model, stem_count=count)
    probe.assert_not_called()
    assert not (local / 'output').exists()


@pytest.mark.parametrize('frozen', [False, True])
def test_operator_local_repository_is_not_a_checkpoint_permission(local, monkeypatch, frozen):
    from app import plugins
    monkeypatch.setattr(plugins.sys, 'frozen', frozen, raising=False)
    monkeypatch.setenv('MTA_DEMUCS_LOCAL_REPO', str(local / 'other-checkpoints'))
    with pytest.raises(ValueError, match='separately reviewed'):
        plugins.DemucsStemSplitter.split(local / 'input', local / 'output', 'htdemucs')
    assert not (local / 'output').exists()


def test_cardinality_profile_cannot_inject_an_unreviewed_model_after_initial_admission(local, monkeypatch):
    from app import plugins
    monkeypatch.setattr(plugins.DemucsStemSplitter, '_model_profiles', lambda: [{'model': 'foreign', 'stem_count': 8}])
    with pytest.raises(ValueError, match='Demucs'):
        plugins.DemucsStemSplitter.split(local / 'input', local / 'output', 'htdemucs', stem_count=8)
    assert not (local / 'output').exists()


@pytest.mark.parametrize('frozen', [False, True])
def test_demucs_revocation_from_progress_callback_prevents_the_actual_launch(local, monkeypatch, frozen):
    from app import plugins
    monkeypatch.setattr(plugins.sys, 'frozen', frozen, raising=False)
    monkeypatch.setattr(plugins.DemucsStemSplitter, 'available', lambda: True)
    monkeypatch.setattr(plugins.subprocess, 'Popen', Mock(side_effect=AssertionError('Revoked model spawned')))
    monkeypatch.setattr('app.demucs_runtime.python_path', lambda: None)
    monkeypatch.setattr(plugins.shutil, 'which', lambda name: None)
    def revoke(*args): permission(local, 'demucs', 'disabled')
    with pytest.raises(policy.LicenseDenied):
        plugins.DemucsStemSplitter.split(local / 'input', local / 'output', 'htdemucs', progress=revoke)
    plugins.subprocess.Popen.assert_not_called()


@pytest.mark.parametrize('frozen', [False, True])
def test_demucs_inference_revocation_prevents_result_delivery_and_preserves_argv(local, monkeypatch, frozen):
    from app import plugins
    monkeypatch.setattr(plugins.sys, 'frozen', frozen, raising=False)
    monkeypatch.setattr(plugins.DemucsStemSplitter, 'available', lambda: True)
    output = local / 'output'
    source = local / 'source.wav'; source.write_bytes(source_audio())
    def model_main():
        permission(local, 'demucs', 'disabled')
        target = output / 'htdemucs' / 'source'; target.mkdir(parents=True)
        (target / 'vocals.wav').write_bytes(source_audio())
    if frozen:
        module = types.ModuleType('demucs.separate'); module.main = model_main
        package = types.ModuleType('demucs'); package.separate = module
        monkeypatch.setitem(sys.modules, 'demucs', package)
        monkeypatch.setitem(sys.modules, 'demucs.separate', module)
    else:
        # This generated operator executable really launches and writes both
        # its output and the policy revocation; no neural weights are loaded.
        python = local / 'test-python'
        python.write_text('#!' + sys.executable + '\nimport pathlib,json,sys,wave\n'
            + 'a=sys.argv;out=pathlib.Path(a[a.index("--out")+1])/a[a.index("-n")+1]/pathlib.Path(a[-1]).stem;out.mkdir(parents=True)\n'
            + 'with wave.open(str(out/"vocals.wav"),"wb") as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(44100);w.writeframes(bytes(128))\n'
            + 'pathlib.Path(' + repr(str(local / 'policy.json')) + ').write_text(json.dumps({"demucs":{"mode":"disabled"}}))\n')
        python.chmod(0o700)
        monkeypatch.setattr('app.demucs_runtime.python_path', lambda: python)
    original_argv = list(sys.argv)
    with pytest.raises(policy.LicenseDenied):
        plugins.DemucsStemSplitter.split(source, output, 'htdemucs')
    assert (output / 'htdemucs/source/vocals.wav').is_file()
    assert sys.argv == original_argv


@pytest.mark.parametrize('filename', [UVR, ROFORMER])
def test_backing_loader_rejects_revocation_before_runtime_load(local, filename):
    from app.backing_vocals_runtime import load_backing_model
    model = 'uvr-kara-2' if filename == UVR else 'audio-separator-weights'
    permission(local, model, 'disabled')
    separator = types.SimpleNamespace(load_model=Mock(side_effect=AssertionError('Disabled model loaded')))
    with pytest.raises(policy.LicenseDenied): load_backing_model(separator, filename)
    separator.load_model.assert_not_called()


@pytest.mark.parametrize('filename', ['/unreviewed/weights.onnx', '../UVR_MDXNET_KARA_2.onnx', 'foreign.onnx', 'operator-provided.ckpt', None])
def test_backing_engine_grant_cannot_authorize_arbitrary_checkpoint_files(local, filename):
    from app.backing_vocals_runtime import load_backing_model
    permission(local, 'audio-separator-weights')
    separator = types.SimpleNamespace(load_model=Mock(side_effect=AssertionError('Unknown file loaded')))
    with pytest.raises(ValueError, match='filename'): load_backing_model(separator, filename)
    separator.load_model.assert_not_called()


def test_backing_load_revocation_cannot_mark_the_cached_runtime_admitted(local):
    from app.backing_vocals_runtime import load_backing_model, separate_backing
    permission(local, 'audio-separator-weights')
    separator = types.SimpleNamespace(
        load_model=lambda **kw: permission(local, 'audio-separator-weights', 'disabled'),
        separate=Mock(side_effect=AssertionError('Revoked loaded model inferred')))
    with pytest.raises(policy.LicenseDenied): load_backing_model(separator, ROFORMER)
    assert separator._mta_backing_filename is None
    permission(local, 'audio-separator-weights')
    with pytest.raises(ValueError, match='admitted checkpoint'): separate_backing(separator, local / 'input', ROFORMER)
    separator.separate.assert_not_called()


def test_loaded_backing_runtime_rechecks_current_permission_and_exact_selector(local):
    from app.backing_vocals_runtime import load_backing_model, separate_backing
    permission(local, 'audio-separator-weights')
    seen = []
    separator = types.SimpleNamespace(load_model=lambda **kw: seen.append(kw), separate=lambda path: ['actual-' + path])
    load_backing_model(separator, ROFORMER)
    assert separate_backing(separator, local / 'input', ROFORMER) == ['actual-' + str(local / 'input')]
    permission(local, 'audio-separator-weights', 'disabled')
    with pytest.raises(policy.LicenseDenied): separate_backing(separator, local / 'input', ROFORMER)
    permission(local, 'uvr-kara-2')
    with pytest.raises(ValueError, match='admitted checkpoint'): separate_backing(separator, local / 'input', UVR)
    assert seen == [{'model_filename': ROFORMER}]


@pytest.mark.parametrize('entry', ['policy', 'native', 'unified'])
@pytest.mark.parametrize('model', ['ffmpeg-center-side', 'mvsep-mega53', 'uvr_mdxnet_kara_2'])
def test_opaque_command_cannot_borrow_dsp_or_other_checkpoint_rights(local, monkeypatch, entry, model):
    monkeypatch.setenv('MTA_LEAD_BACKING_COMMAND', 'arbitrary-binary --input {input}')
    if entry == 'policy': call = lambda: policy.evaluate('backing-vocals', {'model': model})
    elif entry == 'unified':
        from app.ai_unified_adapter import infer
        call = lambda: infer({'kind': 'backing-vocals', 'model': model}, local / 'output' / 'result.wav')
    else:
        from app import main
        probe = Mock(side_effect=AssertionError('Opaque command reached routing/runtime'))
        monkeypatch.setattr(main, '_ai_external_engine', probe)
        call = lambda: main._split_lead_backing_vocals(local / 'input', local / 'output', model_id=model)
    with pytest.raises(policy.LicenseDenied, match='checkpoint rights contract'): call()
    assert not (local / 'output').exists()


def test_opaque_command_rejection_precedes_actual_queue_and_ledger_admission(operator, monkeypatch):
    from app import ai_metering_agent, ai_billing
    monkeypatch.setenv('MTA_LEAD_BACKING_COMMAND', 'arbitrary-binary')
    with ai_billing.db() as c: before = c.execute('SELECT count(*) FROM ai_compute_jobs').fetchone()[0]
    with pytest.raises(policy.LicenseDenied, match='checkpoint rights contract'):
        ai_metering_agent.execute_registered_worker(operator, 'backing-vocals', {'model': 'ffmpeg-center-side'}, source_wav=source_audio())
    with ai_billing.db() as c: assert c.execute('SELECT count(*) FROM ai_compute_jobs').fetchone()[0] == before


@pytest.mark.parametrize('transport', ['json', 'wav'])
def test_actual_token_api_denies_opaque_command_without_worker_or_ledger(env, registered, monkeypatch, transport):
    from app import ai_access, auth
    monkeypatch.setenv('MTA_LEAD_BACKING_COMMAND', 'arbitrary-binary')
    token = ai_access.issue(env, 'opaque separator rejection fixture')
    headers = {'Authorization': 'Bearer ' + token['token']}
    plan = {'model': 'ffmpeg-center-side'}
    with api() as client:
        if transport == 'json':
            response = client.post('/api/ai-jobs/execute', json={'kind': 'backing-vocals', 'plan': plan}, headers=headers)
        else:
            headers.update({'Content-Type': 'audio/wav', 'X-MTA-AI-Options': base64.urlsafe_b64encode(json.dumps(plan).encode()).decode()})
            response = client.post('/api/ai-jobs/execute-audio/backing-vocals', content=source_audio(), headers=headers)
    assert response.status_code == 400 and 'checkpoint rights contract' in response.text
    assert not registered[1].exists()
    with auth.db() as c: assert c.execute('SELECT count(*) FROM ai_compute_jobs').fetchone()[0] == 0


def test_builtin_dsp_actual_child_outputs_preserve_center_side_pcm_and_current_policy(local):
    import numpy as np
    import soundfile as sf
    from app.ai_execution_policy import admitted_env
    source = local / 'source.wav'
    sf.write(source, np.tile([.25, -.25], (2048, 1)), 44100, subtype='PCM_24')
    plan = {'kind': 'backing-vocals', 'model': 'ffmpeg-center-side', 'source_audio': str(source)}
    request = local / 'request.json'; request.write_text(json.dumps(plan))
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, str(root / 'app/ai_unified_adapter.py'),
        '--request', str(request), '--output', str(local / 'result.wav')],
        env={**os.environ, **admitted_env('backing-vocals', policy.evaluate('backing-vocals', plan))},
        cwd=local, capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 0, result.stderr
    lead, sr = sf.read(local / 'lead_vocals.wav'); backing, _ = sf.read(local / 'backing_vocals.wav')
    assert sr == 44100 and lead.shape == backing.shape == (2048, 2)
    np.testing.assert_allclose(lead, 0, atol=2**-22)
    np.testing.assert_allclose(backing[:, 0], .25, atol=2**-22)
    np.testing.assert_allclose(backing[:, 1], -.25, atol=2**-22)
    assert len(json.loads((local / 'output.manifest.json').read_text())['files']) == 2


def test_registered_dsp_cannot_fabricate_single_process_measurement_for_ffmpeg_child(operator, monkeypatch):
    from app import ai_metering_agent, ai_billing
    monkeypatch.delenv('MTA_LEAD_BACKING_COMMAND', raising=False)
    monkeypatch.delenv('MTA_AI_WORKER_BACKING_VOCALS_EXECUTABLE')
    monkeypatch.setenv('MTA_AI_UNIFIED_WORKERS_ENABLED', 'true')
    monkeypatch.setenv('MTA_AI_WORKER_BACKING_VOCALS_PYTHON', sys.executable)
    # Reproduce a short-lived FFmpeg child missed between /proc samples.
    # The known worker topology must still forbid direct-child-only billing.
    monkeypatch.setattr(ai_metering_agent, '_descendants', lambda pid: set())
    with pytest.raises(ai_metering_agent.WorkerUncertain) as error:
        ai_metering_agent.execute_registered_worker(
            operator, 'backing-vocals', {'model': 'ffmpeg-center-side'}, source_wav=source_audio())
    with ai_billing.db() as c:
        row = c.execute('SELECT status,resource_source FROM ai_compute_jobs WHERE id=?', (error.value.job_id,)).fetchone()
        assert row['status'] == 'running' and row['resource_source'] == 'unmetered'
        claim = c.execute('SELECT state FROM regime_worker_claims WHERE operation_id=?', ('job:ledger:' + error.value.job_id,)).fetchone()
        assert claim['state'] == 'running'


def test_backing_revocation_inside_inference_does_not_release_result(local):
    from app.backing_vocals_runtime import load_backing_model, separate_backing
    permission(local, 'audio-separator-weights')
    def infer(path):
        permission(local, 'audio-separator-weights', 'disabled')
        return ['must-not-publish.wav']
    separator = types.SimpleNamespace(load_model=lambda **kw: None, separate=infer)
    load_backing_model(separator, ROFORMER)
    with pytest.raises(policy.LicenseDenied): separate_backing(separator, local / 'source', ROFORMER)


def test_rocm_loaded_callback_rechecks_current_rights_before_every_chunk(local, monkeypatch):
    from contextlib import nullcontext
    from app.backing_vocals_runtime import load_backing_model
    permission(local, 'uvr-kara-2')
    seen = []
    class Model:
        def to(self, device): return self
        def eval(self): return self
        def __call__(self, value): seen.append(value); return value
    class Tensor:
        def to(self, device): return self
        def detach(self): return self
        def cpu(self): return self
        def numpy(self): return 'chunk'
    monkeypatch.setitem(sys.modules, 'torch', types.SimpleNamespace(
        version=types.SimpleNamespace(hip='fixture'), cuda=types.SimpleNamespace(is_available=lambda: True),
        device=lambda value: value, inference_mode=nullcontext))
    monkeypatch.setitem(sys.modules, 'onnx2torch', types.SimpleNamespace(convert=lambda path: Model()))
    instance = types.SimpleNamespace(model_run=lambda x: None, model_path='/fixture/model.onnx')
    separator = types.SimpleNamespace(load_model=lambda **kw: None, model_instance=instance)
    load_backing_model(separator, UVR)
    assert instance.model_run(Tensor()) == 'chunk'
    permission(local, 'uvr-kara-2', 'disabled')
    with pytest.raises(policy.LicenseDenied): instance.model_run(Tensor())
    assert len(seen) == 1


def test_fixed_tool_sharing_metered_group_is_stopped_and_reaped_without_signalling_parent(local):
    from app.separator_process import run
    pidfile = local / 'child-pid'
    code = 'import os,time,pathlib\npathlib.Path(' + repr(str(pidfile)) + ').write_text(os.read(os.open("/proc/self/stat",os.O_RDONLY),100).split()[0].decode())\ntime.sleep(30)\n'
    with pytest.raises(RuntimeError, match='timed out'):
        run([sys.executable, '-c', code], timeout=.3, own_session=False)
    pid = int(pidfile.read_text())
    with pytest.raises(ProcessLookupError): os.kill(pid, 0)
    with pytest.raises(ChildProcessError): os.waitpid(pid, os.WNOHANG)
